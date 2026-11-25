"""The images and the Vulkan driver the user picks for each game.

A library keeps the picks of its games in a file at its root, under each game's path in the library:
the picks follow the library to another mount point or handheld. The file also names the library with
an id, which finds it again at another mount point. The plugin's art.json and drivers.json keep, by
absolute path, the picks of apps, of games outside the libraries, and of libraries it cannot write.
adopt() moves those into the libraries mounted."""
import collections
import os
import uuid

from .jsonfile import read_json, write_json

# The file at the root of each library.
FILE = ".rom-library.json"


def real(path):
    """Return the path with its folder's links resolved. A game file that is a link stays itself."""
    return os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))


class Picks:
    def __init__(self, settings_dir, rom_dirs, log):
        self.art_file = os.path.join(settings_dir, "art.json")
        self.drivers_file = os.path.join(settings_dir, "drivers.json")
        # The image picked for each kind of art and the driver, by absolute path.
        self.art = read_json(self.art_file, {})
        self.drivers = read_json(self.drivers_file, {})
        # Returns the library folders.
        self.rom_dirs = rom_dirs
        self.log = log
        # Each library file read, with its time and size when read.
        self.files = {}

    # Library files

    def place(self, path):
        """Return (library file, the game's path in the library) for a game in a library, else None. A
        game outside the ROM folders read, as after a change of library, belongs to the nearest folder
        above it with a library file."""
        if not path.startswith("/"):
            return None
        game = real(path)
        roots = [os.path.realpath(r.rstrip("/")) for r in self.rom_dirs()]
        root = max((r for r in roots if game.startswith(r + "/")), key=len, default=None)
        folder = os.path.dirname(game)
        while root is None and folder != os.path.dirname(folder):
            if os.path.isfile(os.path.join(folder, FILE)):
                root = folder
            folder = os.path.dirname(folder)
        return (os.path.join(root, FILE), os.path.relpath(game, root)) if root else None

    def load(self, file):
        """Return a library file's content, read again when it changes."""
        try:
            st = os.stat(file)
        except OSError:
            return {}
        key = (st.st_mtime_ns, st.st_size)
        hit = self.files.get(file)
        if hit and hit[0] == key:
            return hit[1]
        data = read_json(file, {})
        data = data if isinstance(data, dict) else {}
        self.files[file] = (key, data)
        return data

    def save(self, file, data):
        """Write a library file. Return False when its drive refuses."""
        data.setdefault("id", uuid.uuid4().hex)
        try:
            write_json(file, data)
        except OSError as e:
            self.log.warning(f"{file}: {e}")
            return False
        self.files.pop(file, None)
        return True

    def library_id(self, root, create=True):
        """Return the id of the library in a folder. Give it one when create is set and the folder can
        be written. Return None otherwise."""
        folder = os.path.realpath(root.rstrip("/"))
        file = os.path.join(folder, FILE)
        found = self.load(file).get("id")
        if found or not create or not os.path.isdir(folder):
            return found
        data = read_json(file, {})
        return data["id"] if self.save(file, data if isinstance(data, dict) else {}) else None

    # A game's picks

    def get(self, path):
        """Return a game's picks: {"art": {kind: image id}, "driver": name or None}."""
        at = self.place(path)
        rec = self.load(at[0]).get("games", {}).get(at[1]) if at else None
        if rec is None:
            return {"art": self.art.get(path, {}), "driver": self.drivers.get(path)}
        return {"art": rec.get("art", {}), "driver": rec.get("driver")}

    def change(self, path, art=None, driver=...):
        """Set the image of each kind in art, and the driver when given. None drops a pick. A game in a
        library gets its picks in the library's file, with those the plugin's files held."""
        rec = self.get(path)
        new = {"art": {k: v for k, v in {**rec["art"], **(art or {})}.items() if v},
               "driver": rec["driver"] if driver is ... else driver}
        at = self.place(path)
        if at and os.path.isdir(os.path.dirname(at[0])):
            file, key = at
            data = read_json(file, {})
            data = data if isinstance(data, dict) else {}
            games = data.setdefault("games", {})
            stored = {k: v for k, v in new.items() if v}
            if stored:
                games[key] = stored
            else:
                games.pop(key, None)
            if self.save(file, data):
                self.drop(path)
                return
        self.keep(path, new)

    def forget(self, path):
        """Drop a game's picks."""
        self.change(path, {k: None for k in self.get(path)["art"]}, None)

    def move(self, old, new):
        """Give a game's picks to the same game at another path."""
        rec = self.get(old)
        if rec["art"] or rec["driver"]:
            self.forget(old)
            self.change(new, rec["art"], rec["driver"])

    # The plugin's files

    def paths(self):
        """Return the games the plugin's files hold picks for."""
        return sorted(p for p in {*self.art, *self.drivers} if p.startswith("/"))

    def keep(self, path, rec):
        """Keep a game's picks in the plugin's files."""
        if rec["art"]:
            self.art[path] = rec["art"]
        else:
            self.art.pop(path, None)
        if rec["driver"]:
            self.drivers[path] = rec["driver"]
        else:
            self.drivers.pop(path, None)
        write_json(self.art_file, self.art)
        write_json(self.drivers_file, self.drivers)

    def drop(self, path):
        if self.art.pop(path, None) is not None:
            write_json(self.art_file, self.art)
        if self.drivers.pop(path, None) is not None:
            write_json(self.drivers_file, self.drivers)

    def rebase(self, old, new):
        """Move the picks the plugin's files hold under the folder old to the folder new."""
        for table, file in ((self.art, self.art_file), (self.drivers, self.drivers_file)):
            moved = {p: new + p[len(old):] for p in table if p.startswith(old + "/")}
            for p, q in moved.items():
                table[q] = table.pop(p)
            if moved:
                write_json(file, table)

    def adopt(self):
        """Move the picks the plugin's files hold for games now in a library into its file. A library
        the plugin cannot write keeps them out. Return how many games moved."""
        waiting = collections.defaultdict(list)
        for path in {*self.art, *self.drivers}:
            at = self.place(path)
            if at and os.path.lexists(path):
                waiting[at[0]].append((path, at[1]))
        moved = 0
        for file, games in waiting.items():
            data = read_json(file, {})
            data = data if isinstance(data, dict) else {}
            table = data.setdefault("games", {})
            for path, key in games:
                rec = table.get(key, {})
                art = {**rec.get("art", {}), **self.art.get(path, {})}
                driver = self.drivers.get(path) or rec.get("driver")
                table[key] = {k: v for k, v in (("art", art), ("driver", driver)) if v}
            if self.save(file, data):
                for path, _ in games:
                    self.art.pop(path, None)
                    self.drivers.pop(path, None)
                moved += len(games)
        if moved:
            write_json(self.art_file, self.art)
            write_json(self.drivers_file, self.drivers)
        return moved
