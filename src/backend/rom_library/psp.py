"""Facts from a PSP disc image: the title, disc id and version in PSP_GAME/PARAM.SFO."""
import struct

from . import disc

# The third letter of a disc id.
REGIONS = {"E": "Europe", "U": "USA", "J": "Japan", "A": "Asia", "K": "Korea", "H": "Hong Kong"}


class Unreadable(Exception):
    pass


def parse_sfo(data):
    """Return {key: text or number} from a PARAM.SFO file."""
    if data[:4] != b"\0PSF":
        raise Unreadable("not a PARAM.SFO")
    keys, values, count = struct.unpack("<III", data[8:20])
    out = {}
    for i in range(min(count, 256)):
        key_at, kind, length, _, value_at = struct.unpack("<HHIII", data[20 + 16 * i:36 + 16 * i])
        start = keys + key_at
        key = data[start:data.index(b"\0", start)].decode("ascii", "replace")
        raw = data[values + value_at:values + value_at + length]
        out[key] = struct.unpack("<I", raw[:4])[0] if kind == 0x0404 else raw.split(b"\0")[0].decode("utf-8", "replace")
    return out


def read(path):
    d = disc.open_disc(path)
    try:
        sfo = disc.iso_file(d, "PSP_GAME/PARAM.SFO")
    finally:
        d.close()
    if not sfo:
        raise Unreadable("no PSP_GAME/PARAM.SFO")
    p = parse_sfo(sfo)
    serial = str(p.get("DISC_ID", "")).strip()
    out = {
        "title": str(p.get("TITLE", "")).strip(),
        "serial": f"{serial[:4]}-{serial[4:]}" if len(serial) == 9 else serial,
        "region": REGIONS.get(serial[2:3]) if serial[:1] in "UN" else None,
        "version": str(p.get("DISC_VERSION", "")).strip(),
        # UC discs are Sony's own: other publishers' discs start with UL.
        "publisher": "Sony Computer Entertainment" if serial.startswith("UC") else None,
    }
    return {k: v for k, v in out.items() if v}
