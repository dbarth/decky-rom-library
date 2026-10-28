"""Game facts from libretro's database: the .rdb files RetroArch ships, read without the network."""
import os
import re

# Where RetroArch keeps its database: the Flatpak's own copy first, then an updated one.
DIRS = [
    "~/.local/share/flatpak/app/org.libretro.RetroArch/current/active/files/share/libretro/database/rdb",
    "/var/lib/flatpak/app/org.libretro.RetroArch/current/active/files/share/libretro/database/rdb",
    "~/.var/app/org.libretro.RetroArch/config/retroarch/database/rdb",
    "~/.config/retroarch/database/rdb",
    "/usr/share/libretro/database/rdb",
]
FIELDS = {"releaseyear": "year", "publisher": "publisher", "developer": "developer", "genre": "genre"}
TAGS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")


class Unreadable(Exception):
    pass


def _value(b, i):
    """Decode one MessagePack value at i. Return (value, next index)."""
    t = b[i]
    if t <= 0x7F:
        return t, i + 1
    if 0x80 <= t <= 0x8F:
        return _map(b, i + 1, t & 0x0F)
    if 0x90 <= t <= 0x9F:
        return _array(b, i + 1, t & 0x0F)
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return b[i + 1:i + 1 + n].decode("utf-8", "replace"), i + 1 + n
    if t == 0xC0:
        return None, i + 1
    if t in (0xC2, 0xC3):
        return t == 0xC3, i + 1
    if t in (0xCC, 0xCD, 0xCE, 0xCF):
        w = 1 << (t - 0xCC)
        return int.from_bytes(b[i + 1:i + 1 + w], "big"), i + 1 + w
    if t in (0xC4, 0xC5, 0xC6, 0xD9, 0xDA, 0xDB):
        w = {0xC4: 1, 0xC5: 2, 0xC6: 4, 0xD9: 1, 0xDA: 2, 0xDB: 4}[t]
        n = int.from_bytes(b[i + 1:i + 1 + w], "big")
        raw = b[i + 1 + w:i + 1 + w + n]
        # Checksums and serials are binary: only text matters here.
        return (raw.decode("utf-8", "replace") if t >= 0xD9 else None), i + 1 + w + n
    if t in (0xDC, 0xDD, 0xDE, 0xDF):
        w = 2 if t in (0xDC, 0xDE) else 4
        n = int.from_bytes(b[i + 1:i + 1 + w], "big")
        return (_array if t <= 0xDD else _map)(b, i + 1 + w, n)
    raise Unreadable(f"MessagePack type {t:#x}")


def _map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = _value(b, i)
        v, i = _value(b, i)
        out[k] = v
    return out, i


def _array(b, i, n):
    out = []
    for _ in range(n):
        v, i = _value(b, i)
        out.append(v)
    return out, i


def read(path):
    """Return the entries of an .rdb file: a header, then one MessagePack map per game, then nil."""
    with open(path, "rb") as f:
        b = f.read()
    if b[:7] != b"RARCHDB":
        raise Unreadable(f"{path} is not a libretro database")
    entries, i = [], 16
    while i < len(b) and b[i] != 0xC0:
        entry, i = _value(b, i)
        if not isinstance(entry, dict):
            break
        entries.append(entry)
    return entries


def key(title):
    """Return a title without its tags, for matching file names against database names."""
    return re.sub(r"[^a-z0-9]+", " ", TAGS.sub("", title).lower()).strip()


def agreed(entries):
    """Return the facts all the entries agree on: two releases with different years give none."""
    out = {}
    for field, name in FIELDS.items():
        values = {e.get(field) for e in entries if e.get(field)}
        if len(values) == 1:
            out[name] = values.pop()
    return out


class Facts:
    def __init__(self, home, log):
        self.home = home
        self.log = log
        # {libretro name: ({rom name: [entries]}, {title key: [entries]})}, None when missing.
        self.index = {}

    def path(self, name):
        for d in DIRS:
            p = os.path.join(self.home + d[1:] if d.startswith("~") else d, f"{name}.rdb")
            if os.path.isfile(p):
                return p
        return None

    def load(self, name):
        if name not in self.index:
            self.index[name] = None
            p = self.path(name)
            if p:
                try:
                    by_rom, by_title = {}, {}
                    for e in read(p):
                        if not any(e.get(f) for f in FIELDS):
                            continue
                        if e.get("rom_name"):
                            by_rom.setdefault(e["rom_name"].lower(), []).append(e)
                        if e.get("name"):
                            by_title.setdefault(key(e["name"]), []).append(e)
                    self.index[name] = (by_rom, by_title)
                except (OSError, Unreadable, IndexError) as e:
                    self.log.warning(f"libretro database {p}: {e}")
        return self.index[name]

    def lookup(self, name, file, titles):
        """Return {year, publisher, developer, genre} for a game, from its file name or else its titles."""
        index = self.load(name)
        if not index:
            return {}
        by_rom, by_title = index
        found = by_rom.get(file.lower())
        if found:
            return agreed(found)
        for title in titles:
            found = by_title.get(key(title))
            if found:
                return agreed(found)
        return {}
