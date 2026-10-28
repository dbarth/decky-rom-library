"""Facts from the header of a Nintendo 64 ROM, also inside a zip: the internal title, the game code
and the revision."""
import os
import zipfile

from .names import REGION_LETTERS

EXTENSIONS = (".z64", ".n64", ".v64", ".bin", ".rom")


class Unreadable(Exception):
    pass


def first_bytes(path, size=0x40):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            roms = [i for i in z.infolist() if i.filename.lower().endswith(EXTENSIONS)]
            if not roms:
                raise Unreadable("no ROM in the zip")
            with z.open(max(roms, key=lambda i: i.file_size)) as f:
                return f.read(size)
    with open(path, "rb") as f:
        return f.read(size)


def big_endian(head):
    """Return the header in the cartridge's byte order, from a z64, v64 or n64 dump."""
    magic = head[:4]
    if magic == b"\x80\x37\x12\x40":
        return head
    if magic == b"\x37\x80\x40\x12":
        return bytes(b for i in range(0, len(head) - 1, 2) for b in (head[i + 1], head[i]))
    if magic == b"\x40\x12\x37\x80":
        return bytes(b for i in range(0, len(head) - 3, 4) for b in reversed(head[i:i + 4]))
    raise Unreadable("no N64 header")


def read(path):
    head = big_endian(first_bytes(path))
    code = head[0x3B:0x3F].decode("ascii", "replace")
    out = {
        "title": head[0x20:0x34].split(b"\0")[0].decode("cp932", "replace").strip(),
        "serial": code if code.isalnum() else None,
        "region": REGION_LETTERS.get(code[3:4]),
        "version": f"Revision {head[0x3F]}" if head[0x3F] else None,
    }
    if code[:1] in ("D", "E"):
        out["media"] = "64DD"
    return {k: v for k, v in out.items() if v}
