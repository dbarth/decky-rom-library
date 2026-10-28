"""Read the 2048-byte sectors of a disc image, ISO, CSO or CHD, and find files in its ISO 9660 tree."""
import struct
import zlib

from . import chd

SECTOR = 2048


class Unreadable(Exception):
    pass


class Plain:
    """An ISO image: 2048-byte sectors, or raw 2352-byte ones with the user data at 16 or 24."""

    def __init__(self, path, raw=False, mode2=False):
        self.f = open(path, "rb")
        self.raw, self.skip = raw, 24 if mode2 else 16

    def sectors(self, lba, count):
        if not self.raw:
            self.f.seek(lba * SECTOR)
            return self.f.read(count * SECTOR)
        out = bytearray()
        for i in range(count):
            self.f.seek((lba + i) * 2352 + self.skip)
            out += self.f.read(SECTOR)
        return bytes(out)

    def close(self):
        self.f.close()


class Cso:
    """A CISO image of the PSP: a table of block offsets, the top bit set on a block stored as is."""

    def __init__(self, path):
        self.f = open(path, "rb")
        head = self.f.read(24)
        if head[:4] != b"CISO":
            raise Unreadable("not a CSO image")
        total, self.block, version, self.align = struct.unpack("<QIBB", head[8:22])
        blocks = (total + self.block - 1) // self.block
        self.index = struct.unpack(f"<{blocks + 1}I", self.f.read(4 * (blocks + 1)))

    def read_block(self, n):
        start, end = self.index[n], self.index[n + 1]
        stored = start >> 31
        start, end = (start & 0x7FFFFFFF) << self.align, (end & 0x7FFFFFFF) << self.align
        self.f.seek(start)
        data = self.f.read(end - start)
        return data[:self.block] if stored else zlib.decompressobj(-15).decompress(data, self.block)

    def sectors(self, lba, count):
        out = bytearray()
        for offset in range(lba * SECTOR, (lba + count) * SECTOR, self.block):
            out += self.read_block(offset // self.block)
        start = lba * SECTOR % self.block
        return bytes(out[start:start + count * SECTOR])

    def close(self):
        self.f.close()


class ChdDisc:
    """A CHD image of a DVD, or of a CD from its first data track on."""

    def __init__(self, path, track=None):
        self.c = chd.Chd(path)
        self.first, self.skip = 0, 16
        if self.c.unit_bytes == chd.CD_FRAME:
            tracks = [t for t in self.c.tracks() if t["type"] != "AUDIO"]
            if track is not None:
                tracks = [t for t in tracks if t["track"] == track]
            if not tracks:
                raise Unreadable("no data track")
            self.first = tracks[0]["start"]
            self.skip = 24 if tracks[0]["type"].startswith("MODE2") else 16
            self.cd = True
        else:
            self.cd = False

    def sectors(self, lba, count):
        if not self.cd:
            return self.c.read(lba * SECTOR, count * SECTOR)
        out = bytearray()
        for i in range(count):
            frame = self.c.frame(self.first + lba + i)
            out += frame[self.skip:self.skip + SECTOR]
        return bytes(out)

    def close(self):
        self.c.close()


def open_disc(path, track=None):
    with open(path, "rb") as f:
        magic = f.read(8)
    if magic == b"MComprHD":
        return ChdDisc(path, track)
    if magic[:4] == b"CISO":
        return Cso(path)
    return Plain(path)


def directory(disc, lba, size):
    """Return {NAME: (lba, size, is folder)} for one ISO 9660 directory."""
    data = disc.sectors(lba, (size + SECTOR - 1) // SECTOR)
    out, i = {}, 0
    while i < len(data):
        length = data[i]
        if length == 0:
            i = (i // SECTOR + 1) * SECTOR
            continue
        extent, extent_size = struct.unpack("<I", data[i + 2:i + 6])[0], struct.unpack("<I", data[i + 10:i + 14])[0]
        name = data[i + 33:i + 33 + data[i + 32]].decode("ascii", "replace").split(";")[0]
        if name not in ("\0", "\1"):
            out[name.upper()] = (extent, extent_size, bool(data[i + 25] & 2))
        i += length
    return out


def iso_file(disc, path):
    """Return the bytes of a file in the ISO 9660 tree, or None."""
    pvd = disc.sectors(16, 1)
    if pvd[1:6] != b"CD001":
        raise Unreadable("no ISO 9660 volume")
    lba, size = struct.unpack("<I", pvd[158:162])[0], struct.unpack("<I", pvd[166:170])[0]
    parts = path.upper().split("/")
    for i, part in enumerate(parts):
        found = directory(disc, lba, size).get(part)
        if not found or found[2] != (i < len(parts) - 1):
            return None
        lba, size, _ = found
    if size > 16 << 20:
        raise Unreadable(f"{path} is too large")
    return disc.sectors(lba, (size + SECTOR - 1) // SECTOR)[:size]
