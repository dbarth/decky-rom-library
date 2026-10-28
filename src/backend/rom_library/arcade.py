"""Arcade facts: FinalBurn Neo's own for each set, and the description and history of each machine
from Arcade-History's history.xml, which the plugin downloads when a new version is out."""
import json
import os
import re
import sqlite3
import threading
import time
import xml.parsers.expat
import zipfile
import zlib

from . import web

DOWNLOAD_PAGE = "https://www.arcade-history.com/index.php?page=download"
SITE = "https://www.arcade-history.com/"
ARCHIVE = re.compile(r"dats/history(\d+)\.zip")
SECTION = re.compile(r"^- ([A-Z][A-Z0-9 &'/-]+) -$")
# The line before the description: "Galaga (c) 1981 Namco."
COPYRIGHT = re.compile(r"\(c\) \d{4}")
FACT = re.compile(r"^(Players|Control|Buttons)\s*:\s*(.+)$", re.M)
# A clone's entry often sends the reader to the original release.
POINTER = re.compile(r"For more information about the game itself[^.]*\.?(?:\s*\"[^\"]*\"\.?)?")
# Sections that point elsewhere or ask for help.
SKIPPED = {"SOURCES", "CONTRIBUTE"}
# How long a check of the download page holds.
CHECK_EVERY = 12 * 3600


class Fbneo:
    """FinalBurn Neo's facts by set, from src/backend/defaults/facts/fbneo.json."""

    def __init__(self, path):
        self.path = path
        self.sets = None
        self.clones = None

    def load(self):
        if self.sets is None:
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.sets = json.load(f)
            except (OSError, ValueError):
                self.sets = {}
            self.clones = {}
            for name, facts in sorted(self.sets.items()):
                if facts.get("parent"):
                    self.clones.setdefault(facts["parent"], []).append(name)
        return self.sets

    def get(self, name):
        return self.load().get(name)

    def family(self, name):
        """Return the parent of a set, then the parent's other clones."""
        parent = (self.get(name) or {}).get("parent") or name
        return [n for n in [parent, *self.clones.get(parent, [])] if n != name]


def split(text):
    """Return (description, [(section, text)]) from one history.xml text.

    The text opens with a line of the machine's age, then "Title (c) year maker.", then the
    description, then sections under "- NAME -" lines."""
    lines = text.replace("\r", "").split("\n")
    if lines and lines[0].rstrip().endswith(":"):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    if lines and COPYRIGHT.search(lines[0]):
        lines = lines[1:]
    description, sections, current = [], [], None
    for line in lines:
        m = SECTION.match(line.strip())
        if m:
            current = [m.group(1).title(), []]
            sections.append(current)
        elif current:
            current[1].append(line)
        else:
            description.append(line)
    tidy = lambda block: re.sub(r"\n{3,}", "\n\n", "\n".join(block)).strip()
    return tidy(description), [(name, tidy(body)) for name, body in sections
                               if name.upper() not in SKIPPED and tidy(body)]


def facts(text):
    """Return the description, the other sections and the players, controls and buttons history.xml
    gives for a machine."""
    description, sections = split(text)
    out = {"description": description, "sections": sections}
    technical = next((body for name, body in sections if name == "Technical"), "")
    for key, value in FACT.findall(technical):
        out.setdefault(key.lower(), re.sub(r"\s+", " ", value).strip().rstrip("."))
    return {k: v for k, v in out.items() if v}


def buttons(value):
    """Say "1 button (FIRE)" for history.xml's "1 (FIRE)"."""
    m = re.match(r"(\d+)\s*(.*)", value or "")
    if not m:
        return value
    count = int(m.group(1))
    return f"{count} button{'' if count == 1 else 's'}" + (f" {m.group(2)}" if m.group(2) else "")


class History:
    def __init__(self, folder, log):
        self.folder = folder
        self.log = log
        self.db_path = os.path.join(folder, "history.db")
        self.state_path = os.path.join(folder, "history.json")
        self.lock = threading.Lock()

    def state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def version(self):
        return self.state().get("version")

    def latest(self):
        """Return (version, url) of the newest history.xml on Arcade-History's download page."""
        with web.urlopen(DOWNLOAD_PAGE, timeout=20) as r:
            page = r.read().decode("utf-8", "replace")
        found = sorted({int(v) for v in ARCHIVE.findall(page)})
        if not found:
            raise ValueError("no history.xml link on the download page")
        return found[-1], f"{SITE}dats/history{found[-1]}.zip"

    def check(self, force=False):
        """Download and index history.xml when the site has a newer version. Ask the site at most
        every 12 hours unless forced. Return True on a change."""
        state = self.state()
        indexed = os.path.isfile(self.db_path)
        if not force and indexed and time.time() - state.get("checked", 0) < CHECK_EVERY:
            return False
        version, url = self.latest()
        changed = not indexed or (state.get("version") or 0) < version
        if changed:
            archive = os.path.join(self.folder, "history.zip")
            os.makedirs(self.folder, exist_ok=True)
            with web.urlopen(url, timeout=120) as r, open(archive + ".tmp", "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            os.replace(archive + ".tmp", archive)
            count = self.index(archive)
            os.remove(archive)
            self.log.info(f"history.xml {version}: {count} machines")
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"version": version if changed else state.get("version"), "checked": time.time()}, f)
        return changed

    def index(self, archive):
        """Store each machine's text, compressed, by every set name its entry lists."""
        os.makedirs(self.folder, exist_ok=True)
        tmp = self.db_path + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
        db = sqlite3.connect(tmp)
        db.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, body BLOB)")
        db.execute("CREATE TABLE names (name TEXT PRIMARY KEY, text INTEGER)")
        state = {"systems": [], "text": [], "in_text": False, "entries": 0}

        def start(tag, attrs):
            if tag == "entry":
                state["systems"], state["text"] = [], []
            elif tag == "system" and "name" in attrs:
                state["systems"].append(attrs["name"])
            elif tag == "text":
                state["in_text"] = True

        def end(tag):
            if tag == "text":
                state["in_text"] = False
            elif tag == "entry" and state["systems"]:
                body = zlib.compress("".join(state["text"]).encode("utf-8"))
                row = db.execute("INSERT INTO texts (body) VALUES (?)", (body,)).lastrowid
                db.executemany("INSERT OR IGNORE INTO names VALUES (?, ?)", [(n, row) for n in state["systems"]])
                state["entries"] += 1

        def data(text):
            if state["in_text"]:
                state["text"].append(text)

        parser = xml.parsers.expat.ParserCreate("UTF-8")
        parser.StartElementHandler, parser.EndElementHandler, parser.CharacterDataHandler = start, end, data
        with zipfile.ZipFile(archive) as z:
            name = next(n for n in z.namelist() if n.endswith("history.xml"))
            with z.open(name) as f:
                parser.ParseFile(f)
        db.commit()
        db.close()
        with self.lock:
            os.replace(tmp, self.db_path)
        return state["entries"]

    def text(self, *names):
        """Return the text of the first name history.xml knows, or None."""
        if not os.path.isfile(self.db_path):
            return None
        with self.lock:
            db = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            try:
                for name in names:
                    if not name:
                        continue
                    row = db.execute("SELECT body FROM texts JOIN names ON names.text = texts.id WHERE names.name = ?",
                                     (name,)).fetchone()
                    if row:
                        return zlib.decompress(row[0]).decode("utf-8")
            finally:
                db.close()
        return None


class Arcade:
    def __init__(self, facts_path, folder, log):
        self.fbneo = Fbneo(facts_path)
        self.history = History(folder, log)

    def history_facts(self, name):
        """Return what history.xml says of a set or its parent. A clone's entry that points to the
        original release gets the original's description, the longest of its family, after its own note."""
        own = self.history.text(name, (self.fbneo.get(name) or {}).get("parent"))
        if not own:
            return {}
        got = facts(own)
        if not POINTER.search(own):
            return got
        best = None
        for other in self.fbneo.family(name):
            text = self.history.text(other)
            if text and not POINTER.search(text):
                found = facts(text)
                if len(found.get("description", "")) > len((best or {}).get("description", "")):
                    best = found
        if not best:
            return got
        note = POINTER.sub("", got.get("description", "")).strip()
        best["description"] = (note + "\n\n" if note else "") + best["description"]
        return {**best, **{k: v for k, v in got.items() if k in ("players", "control", "buttons")}}

    def layers(self, name):
        """Return [("fbneo", facts), ("history", facts)] for one set: FinalBurn Neo's, then history.xml's."""
        own = self.fbneo.get(name) or {}
        fbneo = {
            "released": own.get("year"),
            "manufacturer": own.get("maker"),
            "board": own.get("board"),
            "players": str(own["players"]) if own.get("players") else None,
            "genre": ", ".join(own.get("genres", [])),
            "broken": own.get("broken"),
            "vertical": own.get("vertical"),
        }
        got = self.history_facts(name)
        history = {
            "description": got.get("description"),
            "sections": got.get("sections"),
            "controls": [c for c in (got.get("control"), buttons(got.get("buttons"))) if c],
            "players": got.get("players"),
        }
        return [("fbneo", {k: v for k, v in fbneo.items() if v}), ("history", {k: v for k, v in history.items() if v})]

    def facts(self, name):
        """Return what FinalBurn Neo and history.xml say of one set, FinalBurn Neo first."""
        out = {}
        for _, facts in self.layers(name):
            out = {**facts, **out}
        return out
