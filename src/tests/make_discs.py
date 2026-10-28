"""Build the small disc images of tests/fixtures/discs: a PSP ISO with a PARAM.SFO, a Dreamcast GDI
with an IP.BIN, and their CHDs, one per codec. The CHDs need MAME's chdman.

Usage: python3 tests/make_discs.py"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from rom_library import chd  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "discs")
SECTOR = 2048


def both16(n):
    return struct.pack("<H", n) + struct.pack(">H", n)


def both32(n):
    return struct.pack("<I", n) + struct.pack(">I", n)


def record(name, lba, size, folder):
    """One ISO 9660 directory record."""
    raw = name if isinstance(name, bytes) else name.encode("ascii")
    body = (both32(lba) + both32(size) + bytes(7) + bytes([2 if folder else 0, 0, 0]) + both16(1)
            + bytes([len(raw)]) + raw)
    length = 1 + 1 + len(body) + (len(raw) + 1) % 2
    return (bytes([length, 0]) + body).ljust(length, b"\0")


def iso(files):
    """Return an ISO 9660 image of one folder level: {"DIR/FILE": bytes}."""
    folders = sorted({p.split("/")[0] for p in files if "/" in p})
    root_lba, next_lba = 20, 21 + len(folders)
    data, layout = {}, {}
    for path, content in sorted(files.items()):
        layout[path] = (next_lba, len(content))
        data[next_lba] = content
        next_lba += (len(content) + SECTOR - 1) // SECTOR
    total = next_lba
    root = record(b"\0", root_lba, SECTOR, True) + record(b"\1", root_lba, SECTOR, True)
    sectors = {}
    for i, folder in enumerate(folders):
        lba = root_lba + 1 + i
        root += record(folder, lba, SECTOR, True)
        body = record(b"\0", lba, SECTOR, True) + record(b"\1", root_lba, SECTOR, True)
        for path, (at, size) in sorted(layout.items()):
            if path.startswith(folder + "/"):
                body += record(path.split("/")[1] + ";1", at, size, False)
        sectors[lba] = body
    for path, (at, size) in sorted(layout.items()):
        if "/" not in path:
            root += record(path + ";1", at, size, False)
    sectors[root_lba] = root
    pvd = bytearray(SECTOR)
    pvd[0:6] = b"\x01CD001"
    pvd[6] = 1
    pvd[40:72] = b"TEST".ljust(32)
    pvd[80:88] = both32(total)
    pvd[120:124] = both16(1)
    pvd[128:132] = both16(SECTOR)
    pvd[156:156 + 34] = record(b"\0", root_lba, SECTOR, True)
    out = bytearray(total * SECTOR)
    out[16 * SECTOR:17 * SECTOR] = pvd
    out[17 * SECTOR:17 * SECTOR + 7] = b"\xffCD001\x01"
    for lba, body in {**sectors, **data}.items():
        out[lba * SECTOR:lba * SECTOR + len(body)] = body
    return bytes(out)


def sfo(entries):
    keys, values, table = b"", b"", b""
    for key, value in entries:
        raw = value.encode("utf-8") + b"\0" if isinstance(value, str) else struct.pack("<I", value)
        size = (len(raw) + 3) // 4 * 4
        kind = 0x0204 if isinstance(value, str) else 0x0404
        table += struct.pack("<HHIII", len(keys), kind, len(raw), size, len(values))
        keys += key.encode("ascii") + b"\0"
        values += raw.ljust(size, b"\0")
    keys = keys.ljust((len(keys) + 3) // 4 * 4, b"\0")
    start = 20 + len(table)
    return b"\0PSF" + struct.pack("<IIII", 0x101, start, start + len(keys), len(entries)) + table + keys + values


def ip_bin():
    fields = [
        b"SEGA SEGAKATANA ", b"SEGA ENTERPRISES", b"1234 GD-ROM1/1  ", b"  E     ", b"0F00A00 ",
        b"MK-0000000", b"V1.001", b"20000714        ", b"1ST_READ.BIN    ", b"TEST COMPANY    ",
        b"TEST GAME".ljust(128),
    ]
    return b"".join(fields).ljust(0x8000, b"\0")


def mode1(user):
    """A raw 2352-byte sector around 2048 bytes of user data, with its ECC: chdman then drops the
    ECC, and the reader must rebuild it."""
    sector = bytearray(chd.SYNC + b"\x00\x02\x00\x01" + user.ljust(SECTOR, b"\0") + bytes(288))
    chd.fill_ecc(sector)
    return bytes(sector)


def noise(n, seed):
    """Bytes that compress a little, so that chdman keeps each codec it is given."""
    out, x = bytearray(), seed
    for i in range(n):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        out.append(65 + (x >> 16) % 8)
    return bytes(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    psp = iso({
        "PSP_GAME/PARAM.SFO": sfo([("CATEGORY", "UG"), ("DISC_ID", "UCES00001"), ("DISC_VERSION", "1.01"),
                                   ("PARENTAL_LEVEL", 5), ("TITLE", "Test Game®: Portable")]),
        "PSP_GAME/FILLER.BIN": noise(16 * SECTOR, 7),
        "UMD_DATA.BIN": b"UCES-00001|0000000000000001|0001|G",
    })
    with open(os.path.join(OUT, "psp.iso"), "wb") as f:
        f.write(psp)
    with tempfile.TemporaryDirectory() as tmp:
        user = ip_bin() + noise(SECTOR * 8, 3)
        tracks = {
            "track01.bin": mode1(noise(SECTOR, 1)) + mode1(b"") * 299,
            "track02.raw": bytes(2352 * 302),
            "track03.bin": b"".join(mode1(user[i * SECTOR:(i + 1) * SECTOR]) for i in range(24)),
        }
        for name, data in tracks.items():
            with open(os.path.join(tmp, name), "wb") as f:
                f.write(data)
        gdi = os.path.join(tmp, "disc.gdi")
        with open(gdi, "w") as f:
            f.write("3\n1 0 4 2352 track01.bin 0\n2 450 0 2352 track02.raw 0\n3 45000 4 2352 track03.bin 0\n")
        os.makedirs(os.path.join(OUT, "gdi"), exist_ok=True)
        shutil.copy(gdi, os.path.join(OUT, "gdi", "disc.gdi"))
        with open(os.path.join(OUT, "gdi", "track03.bin"), "wb") as f:
            f.write(tracks["track03.bin"][:2352 * 2])
        for codec in ("cdlz", "cdzl"):
            subprocess.run(["chdman", "createcd", "-f", "-c", codec, "-i", gdi,
                            "-o", os.path.join(OUT, f"dreamcast-{codec}.chd")], check=True, capture_output=True)
        for codec in ("lzma", "zlib", "huff"):
            subprocess.run(["chdman", "createdvd", "-f", "-c", codec, "-i", os.path.join(OUT, "psp.iso"),
                            "-o", os.path.join(OUT, f"psp-{codec}.chd")], check=True, capture_output=True)


if __name__ == "__main__":
    main()
