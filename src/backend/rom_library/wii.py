"""Facts from the disc header of a Wii or GameCube image: the game id, the maker code, the disc
number, the version and the internal title. Reads ISO, GCM, RVZ, WIA, WBFS, CISO and GCZ."""
import struct
import zlib

from .names import REGION_LETTERS

WII_MAGIC = 0x5D1C9EA3
GC_MAGIC = 0xC2339F3D
# Nintendo's two-character licensee codes, for the publishers whose code is well known.
MAKERS = {
    "01": "Nintendo", "08": "Capcom", "41": "Ubisoft", "4F": "Eidos", "51": "Acclaim", "52": "Activision",
    "5D": "Midway", "5G": "Majesco", "64": "LucasArts", "69": "Electronic Arts", "70": "Atari", "78": "THQ",
    "7D": "Vivendi", "8P": "Sega", "A4": "Konami", "AF": "Namco", "B2": "Bandai", "C8": "Koei",
    "E9": "Natsume", "EB": "Atlus", "GD": "Square Enix",
}


class Unreadable(Exception):
    pass


def header(path):
    """Return the first 0x80 bytes of the disc, whatever the container."""
    with open(path, "rb") as f:
        head = f.read(0x200)
        if len(head) < 0x80:
            raise Unreadable("short file")
        magic = head[:4]
        if magic in (b"RVZ\x01", b"WIA\x01"):
            # The disc struct follows the 0x48-byte file header and keeps the disc's first 0x80 bytes.
            return head[0x58:0xD8]
        if magic == b"WBFS":
            f.seek(1 << head[8])
            return f.read(0x80)
        if magic == b"CISO":
            # A 0x8000-byte map, then the first block when the map marks it present.
            if not head[8]:
                raise Unreadable("the first CISO block is empty")
            f.seek(0x8000)
            return f.read(0x80)
        if struct.unpack("<I", magic)[0] == 0xB10BC001:
            # GCZ: a block table of u64 offsets, the top bit set on a block stored as is.
            block_size, blocks = struct.unpack("<II", head[24:32])
            pointers = struct.unpack(f"<{min(blocks, 2)}Q", head[32:32 + 8 * min(blocks, 2)])
            stored = pointers[0] >> 63
            start = pointers[0] & ~(1 << 63)
            end = pointers[1] & ~(1 << 63) if len(pointers) > 1 else start + block_size
            f.seek(32 + blocks * 12 + start)
            block = f.read(end - start)
            return (block if stored else zlib.decompress(block))[:0x80]
        return head[:0x80]


def text(raw, japanese):
    return raw.split(b"\0", 1)[0].decode("shift_jis" if japanese else "cp1252", "replace").strip()


def parse(head):
    if len(head) < 0x80:
        raise Unreadable("short disc header")
    wii = struct.unpack(">I", head[0x18:0x1C])[0] == WII_MAGIC
    gc = struct.unpack(">I", head[0x1C:0x20])[0] == GC_MAGIC
    if not (wii or gc):
        raise Unreadable("no Wii or GameCube disc header")
    game_id = head[:6].decode("ascii", "replace")
    out = {
        "title": text(head[0x20:0x80], game_id[3:4] == "J"),
        "serial": game_id,
        "region": REGION_LETTERS.get(game_id[3:4]),
        "publisher": MAKERS.get(game_id[4:6]),
        "version": f"Revision {head[7]}" if head[7] else None,
    }
    if head[6]:
        out["disc"] = head[6] + 1
    return {k: v for k, v in out.items() if v}


def read(path):
    return parse(header(path))


def console(head):
    """Return "wii" or "gc" for a disc header that parse() reads."""
    return "wii" if struct.unpack(">I", head[0x18:0x1C])[0] == WII_MAGIC else "gc"
