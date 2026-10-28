"""What a game's page says about it: the facts of its file first, then its file name's tags, then
ES-DE's scraped facts, then an emulator's database. Decoded files are cached by size and time."""
import os
import threading

from . import dreamcast, n64, psp, switch, wii
from .jsonfile import read_json, write_json

DISC = (".rvz", ".wia", ".iso", ".gcm", ".wbfs", ".ciso", ".gcz")
# The decoder of each ES-DE system and the extensions it reads.
DECODERS = {
    "n64": (n64, (".z64", ".n64", ".v64", ".zip")),
    "n64dd": (n64, (".z64", ".n64", ".v64", ".zip")),
    "switch": (switch, (".nsp", ".xci")),
    "wii": (wii, DISC),
    "gc": (wii, DISC),
    "psp": (psp, (".iso", ".cso", ".chd")),
    "dreamcast": (dreamcast, (".chd", ".gdi", ".iso")),
}
# The fields where a later source may only add precision: a full date over a year.
DATED = ("released",)


def switch_update(root, title_id):
    """Return the update of a Switch title in its system's folder, found by the update's title id in
    brackets in its file name, or None."""
    update = f"[{int(title_id, 16) | 0x800:016X}]".lower()
    for folder, _, names in os.walk(root):
        for name in sorted(names):
            if update in name.lower() and name.lower().endswith((".nsp", ".xci")):
                return os.path.join(folder, name)
    return None


def decodable(sid, path):
    decoder = DECODERS.get(sid)
    return bool(decoder) and os.path.isfile(path) and path.lower().endswith(decoder[1])


def esde_date(value):
    """Return YYYY-MM-DD from ES-DE's 19910206T000000, or YYYY when ES-DE padded a year with 0101."""
    digits = (value or "")[:8]
    if len(digits) != 8 or not digits.isdigit() or digits[:4] == "0000":
        return None
    return digits[:4] if digits[4:] == "0101" else f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def scraped(meta):
    """Return the facts an ES-DE scraper wrote in a game's gamelist entry."""
    try:
        rating = float(meta.get("rating") or 0)
    except ValueError:
        rating = 0
    out = {
        "description": (meta.get("desc") or "").strip(),
        "developer": meta.get("developer"),
        "publisher": meta.get("publisher"),
        "released": esde_date(meta.get("releasedate")),
        "genre": meta.get("genre"),
        "players": meta.get("players"),
        "rating": rating if 0 < rating <= 1 else None,
    }
    return {k: v for k, v in out.items() if v}


def merge(layers):
    """Merge [(source, facts)], first source first. Return the facts and, for each, its source."""
    out, sources = {}, {}
    for source, facts in layers:
        for key, value in facts.items():
            if value in (None, "", [], {}):
                continue
            if key not in out:
                out[key], sources[key] = value, source
            elif key in DATED and len(str(value)) > len(str(out[key])) and str(value).startswith(str(out[key])):
                out[key], sources[key] = value, source
    return out, sources


class Files:
    """The facts decoded from each game file, kept in a JSON file by path, size and time."""

    def __init__(self, cache_file, home, log):
        self.cache_file = cache_file
        self.home = home
        self.log = log
        self.entries = read_json(cache_file, {})
        self.lock = threading.Lock()
        self.keys = None

    def decode(self, sid, path):
        module = DECODERS[sid][0]
        if module is switch:
            if self.keys is None:
                self.keys = switch.find_keys(self.home)
            return switch.read(path, self.home, self.keys)
        return module.read(path)

    def facts(self, sid, path, retry=False):
        """Return the facts of a game file, decoded once per size and time. A failure is kept until
        a retry: the keys or a library may come later."""
        if not decodable(sid, path):
            return {}
        try:
            st = os.stat(path)
        except OSError:
            return {}
        key = [st.st_size, st.st_mtime_ns]
        with self.lock:
            hit = self.entries.get(path)
        if hit and hit["key"] == key and not (retry and "error" in hit):
            return hit.get("facts", {})
        entry = {"key": key}
        try:
            entry["facts"] = self.decode(sid, path)
        # A damaged or unusual file can fail in any parser: it must not break the page.
        except Exception as e:  # noqa: BLE001
            entry["error"] = f"{type(e).__name__}: {e}"
            self.log.warning(f"facts of {os.path.basename(path)}: {entry['error']}")
        with self.lock:
            self.entries[path] = entry
            write_json(self.cache_file, self.entries)
        return entry.get("facts", {})

    def refresh(self, games):
        """Decode the files of [(system, path)] that changed, retry the failures and forget the
        files that are gone. Return (decoded, failed)."""
        self.keys = None
        for sid, path in games:
            self.facts(sid, path, retry=True)
        wanted = {path for _, path in games}
        with self.lock:
            for path in [p for p in self.entries if not os.path.exists(p)]:
                del self.entries[path]
            write_json(self.cache_file, self.entries)
            failed = sum("error" in self.entries[p] for p in wanted if p in self.entries)
        return len(wanted) - failed, failed
