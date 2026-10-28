"""Facts from the IP.BIN of a Dreamcast disc: company, release date, regions, peripherals, product
number, version and title. Reads CHD, GDI and ISO images."""
import os
import re

from . import disc

# The bits of the peripheral field that name something to plug in or show, by bit.
PERIPHERALS = {
    4: "VGA box", 9: "Jump Pack", 10: "Microphone", 11: "VMU", 25: "Light gun", 26: "Keyboard", 27: "Mouse",
}
AREAS = (("J", "Japan"), ("U", "USA"), ("E", "Europe"))
COMPANIES = {"SEGA ENTERPRISES": "Sega"}
GDI_LINE = re.compile(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(?:"([^"]+)"|(\S+))\s+(\d+)')


class Unreadable(Exception):
    pass


def field(ip, start, end):
    return ip[start:end].decode("latin-1").strip()


def parse_ip(ip):
    if ip[:16] != b"SEGA SEGAKATANA ":
        raise Unreadable("no IP.BIN")
    date = field(ip, 0x50, 0x58)
    area = field(ip, 0x30, 0x38)
    try:
        bits = int(field(ip, 0x38, 0x3F), 16)
    except ValueError:
        bits = 0
    company = field(ip, 0x70, 0x80)
    # A third party's disc may hold "SEGA LC-T-12": a licensee code without a name.
    if company.startswith("SEGA LC-"):
        company = None
    disc_of = re.search(r"GD-ROM\s*(\d+)\s*/\s*(\d+)", field(ip, 0x20, 0x30))
    out = {
        "title": field(ip, 0x80, 0x100),
        "publisher": COMPANIES.get(company, company),
        "released": f"{date[:4]}-{date[4:6]}-{date[6:8]}" if re.fullmatch(r"(19|20)\d{6}", date) else None,
        "region": ", ".join(name for letter, name in AREAS if letter in area),
        "serial": field(ip, 0x40, 0x4A),
        "version": field(ip, 0x4A, 0x50),
        "controls": [name for bit, name in sorted(PERIPHERALS.items()) if bits & (1 << bit)],
    }
    if disc_of and int(disc_of.group(2)) > 1:
        out["disc"] = f"{disc_of.group(1)} of {disc_of.group(2)}"
    return {k: v for k, v in out.items() if v}


def gdi_ip(path):
    """Return the first sector of the high-density data track a GDI names."""
    with open(path, errors="replace") as f:
        tracks = [m for m in map(GDI_LINE.match, f.read(1 << 16).splitlines()) if m]
    data = [m for m in tracks if m.group(3) == "4"]
    if not data:
        raise Unreadable("the GDI names no data track")
    m = data[-1]
    track = os.path.join(os.path.dirname(path), m.group(5) or m.group(6))
    with open(track, "rb") as f:
        f.seek(16 if m.group(4) == "2352" else 0)
        return f.read(0x100)


def read(path):
    if path.lower().endswith(".gdi"):
        return parse_ip(gdi_ip(path))
    d = disc.open_disc(path)
    try:
        if isinstance(d, disc.ChdDisc) and d.cd:
            # IP.BIN opens the high-density area of a GD-ROM, and the data track of a CD.
            for track in reversed([t for t in d.c.tracks() if t["type"] != "AUDIO"]):
                frame = d.c.frame(track["start"])
                skip = 24 if track["type"].startswith("MODE2") else 16
                if frame[skip:skip + 16] == b"SEGA SEGAKATANA ":
                    return parse_ip(frame[skip:skip + 0x100])
            raise Unreadable("no IP.BIN in the data tracks")
        return parse_ip(d.sectors(0, 1))
    finally:
        d.close()
