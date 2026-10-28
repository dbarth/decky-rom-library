"""RetroArch's settings for one game. A key in the game's override, config/<core name>/<game>.cfg,
overrides the same key in retroarch.cfg, the core's override and the content folder's override;
removing it brings back their value."""
import os
import re

# Each setting: its key and RetroArch's default.
SETTINGS = {
    "bezel": ("input_overlay_enable", "true"),
    "rewind": ("rewind_enable", "false"),
}
# Run-ahead takes two keys. Properties shows it as a number of frames, "0" when it is off.
RUN_AHEAD, FRAMES = "run_ahead_enabled", "run_ahead_frames"

# The Flatpak's files. A path in /app is in them, seen from inside the Flatpak's sandbox.
FLATPAK = ("~/.local/share/flatpak/app/org.libretro.RetroArch/current/active/files",
           "/var/lib/flatpak/app/org.libretro.RetroArch/current/active/files")

# A line of a .cfg or .info file: key = "value".
LINE = re.compile(r'^\s*([^#\s=]+)\s*=\s*"?([^"]*)"?\s*$')


class RetroArch:
    def __init__(self, home):
        self.home = home
        # The Flatpak's config, else the native one.
        folders = [os.path.join(home, ".var", "app", "org.libretro.RetroArch", "config", "retroarch"),
                   os.path.join(home, ".config", "retroarch")]
        self.folder = next((f for f in folders if os.path.isfile(os.path.join(f, "retroarch.cfg"))), folders[0])
        self.cfg = os.path.join(self.folder, "retroarch.cfg")

    def expand(self, path):
        """Return a path of RetroArch's config on the disk: ~ is the home, /app the Flatpak's files."""
        if path.startswith("~/"):
            return os.path.join(self.home, path[2:])
        if path.startswith("/app/"):
            roots = [self.expand(root) for root in FLATPAK]
            return next((r for r in roots if os.path.isdir(r)), roots[0]) + path[4:]
        return path

    def core_name(self, top, core):
        """Return the name of a core's folder of overrides, read from its .info file, such as FinalBurn
        Neo for fbneo_libretro.so. None when the file is missing."""
        info = os.path.splitext(os.path.basename(core))[0] + ".info"
        for folder in (top.get("libretro_directory"), top.get("libretro_info_path")):
            name = folder and read(os.path.join(self.expand(folder), info)).get("corename")
            if name:
                return name
        return None

    def files(self, core, rom):
        """Return retroarch.cfg's values, the paths of the core's and the content folder's overrides,
        and the game's override. RetroArch names a game's override after its file and a folder's after
        the folder. None when the core has no .info file."""
        top = read(self.cfg)
        name = self.core_name(top, core)
        if not name:
            return None
        folder = os.path.join(self.expand(top.get("rgui_config_directory") or os.path.join(self.folder, "config")),
                              name)
        rom = rom.rstrip("/")
        game = os.path.splitext(os.path.basename(rom))[0]
        parent = os.path.basename(os.path.dirname(rom))
        layers = [os.path.join(folder, f"{name}.cfg"), os.path.join(folder, f"{parent}.cfg")]
        return top, layers, os.path.join(folder, f"{game}.cfg")

    def base(self, core, rom):
        """Return the values a game gets without its override, its override's path and its values."""
        got = self.files(core, rom)
        if not got:
            raise ValueError(f"RetroArch has no .info file for {os.path.basename(core)}")
        top, layers, path = got
        values = dict(top)
        for layer in layers:
            values.update(read(layer))
        return values, path, read(path)

    def settings(self, core, rom):
        """Return the game's settings, None for each one it takes from the others, and theirs. A value
        the same as theirs counts as theirs, as RetroArch saves an override. Also tell whether the game
        shows an overlay, its bezel. None when the core has no .info file."""
        try:
            base, path, game = self.base(core, rom)
        except ValueError:
            return None
        values, globals_ = {}, {}
        for name, (key, default) in SETTINGS.items():
            globals_[name] = base.get(key, default)
            values[name] = game[key] if game.get(key, globals_[name]) != globals_[name] else None
        globals_["run_ahead"] = frames(base)
        own = frames({**base, **game})
        values["run_ahead"] = own if own != globals_["run_ahead"] else None
        overlay = game.get("input_overlay", base.get("input_overlay", ""))
        return {"id": os.path.splitext(os.path.basename(path))[0], "values": values, "globals": globals_,
                "overlay": bool(overlay) and os.path.isfile(self.expand(overlay))}

    def set(self, core, rom, name, value):
        """Set one of the game's settings, or bring back the others' value with None. The game's
        override keeps only the values that differ from the others', and goes when it has none."""
        base, path, _ = self.base(core, rom)
        if name in SETTINGS and value in ("true", "false", None):
            key, default = SETTINGS[name]
            changes = {key: None if value in (None, base.get(key, default)) else value}
        elif name == "run_ahead" and (value is None or value.isdigit()):
            if value in (None, frames(base)):
                changes = {RUN_AHEAD: None, FRAMES: None}
            elif value == "0":
                changes = {RUN_AHEAD: "false", FRAMES: None}
            else:
                changes = {RUN_AHEAD: "true", FRAMES: value}
        else:
            raise ValueError(f"no RetroArch setting {name}={value}")
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            lines = []
        for key, v in changes.items():
            lines = [line for line in lines if not (LINE.match(line) and LINE.match(line)[1] == key)]
            if v is not None:
                lines.append(f'{key} = "{v}"')
        if any(LINE.match(line) for line in lines):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            os.replace(path + ".tmp", path)
        elif os.path.exists(path):
            os.remove(path)


def frames(values):
    """Return the frames run-ahead runs, "0" when it is off."""
    return values.get(FRAMES, "1") if values.get(RUN_AHEAD, "false") == "true" else "0"


def read(path):
    """Return the keys of a .cfg or .info file, else {}."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return {m[1]: m[2] for m in map(LINE.match, f) if m}
    except (FileNotFoundError, NotADirectoryError):
        return {}
