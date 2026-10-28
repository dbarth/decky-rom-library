"""Dolphin's settings for one game. A key in the game's INI, GameSettings/<game id>.ini, overrides the
same key in Dolphin's global INIs; removing it brings back the global value."""
import os
import re

from . import dsu

# Each setting: its section and key in the game's INI, then its global INI, section, key and default.
SETTINGS = {
    "aspect": ("Video_Settings", "AspectRatio", "GFX.ini", "Settings", "AspectRatio", "0"),
    "resolution": ("Video_Settings", "InternalResolution", "GFX.ini", "Settings", "InternalResolution", "1"),
    "backend": ("Core", "GFXBackend", "Dolphin.ini", "Core", "GFXBackend", "OGL"),
    "wiimote": ("Controls", "WiimoteProfile1", None, None, None, None),
}

# The Wii Remote layouts, saved as Dolphin profiles in Profiles/Wiimote. The names are positions on
# the gamepad, as Dolphin's SDL backend gives them: Button S is the bottom face button.
DPAD = {"D-Pad/Up": "`Pad N`", "D-Pad/Down": "`Pad S`", "D-Pad/Left": "`Pad W`", "D-Pad/Right": "`Pad E`"}
MENU = {"Buttons/-": "`Back`", "Buttons/+": "`Start`", "Buttons/Home": "`Thumb R`"}
NUNCHUK = "Wii Remote and Nunchuk"
SIDEWAYS = "Sideways Wii Remote"
CLASSIC = "Classic Controller"
LAYOUTS = {
    NUNCHUK: {
        "Buttons/A": "`Button S`", "Buttons/B": "`Trigger R` | `Button E`", "Buttons/1": "`Button W`",
        "Buttons/2": "`Button N`", **MENU, **DPAD,
        "IR/Up": "`Right Y+`", "IR/Down": "`Right Y-`", "IR/Left": "`Right X-`", "IR/Right": "`Right X+`",
        "Shake/X": "`Shoulder R`", "Shake/Y": "`Shoulder R`", "Shake/Z": "`Shoulder R`",
        "Extension": "Nunchuk",
        "Nunchuk/Buttons/C": "`Shoulder L`", "Nunchuk/Buttons/Z": "`Trigger L`",
        "Nunchuk/Stick/Up": "`Left Y+`", "Nunchuk/Stick/Down": "`Left Y-`",
        "Nunchuk/Stick/Left": "`Left X-`", "Nunchuk/Stick/Right": "`Left X+`",
        "Nunchuk/Shake/X": "`Thumb L`", "Nunchuk/Shake/Y": "`Thumb L`", "Nunchuk/Shake/Z": "`Thumb L`",
    },
    # Dolphin turns the D-pad and the tilt with the remote. The left stick moves too.
    SIDEWAYS: {
        "Buttons/A": "`Button E`", "Buttons/B": "`Trigger R`", "Buttons/1": "`Button W`",
        "Buttons/2": "`Button S`", **MENU,
        "D-Pad/Up": "`Pad N` | `Left Y+`", "D-Pad/Down": "`Pad S` | `Left Y-`",
        "D-Pad/Left": "`Pad W` | `Left X-`", "D-Pad/Right": "`Pad E` | `Left X+`",
        "Shake/X": "`Button N` | `Shoulder R`", "Shake/Y": "`Button N` | `Shoulder R`",
        "Shake/Z": "`Button N` | `Shoulder R`",
        "Tilt/Forward": "`Right Y+`", "Tilt/Backward": "`Right Y-`",
        "Tilt/Left": "`Right X-`", "Tilt/Right": "`Right X+`",
        "Options/Sideways Wiimote": "True", "Extension": "None",
    },
    # The Classic Controller's a, b, x and y sit as on a Nintendo pad: a on the right.
    CLASSIC: {
        **MENU, "Extension": "Classic",
        "Classic/Buttons/a": "`Button E`", "Classic/Buttons/b": "`Button S`",
        "Classic/Buttons/x": "`Button N`", "Classic/Buttons/y": "`Button W`",
        "Classic/Buttons/ZL": "`Trigger L`", "Classic/Buttons/ZR": "`Trigger R`",
        "Classic/Buttons/-": "`Back`", "Classic/Buttons/+": "`Start`", "Classic/Buttons/Home": "`Thumb R`",
        "Classic/Triggers/L": "`Shoulder L`", "Classic/Triggers/R": "`Shoulder R`",
        "Classic/Triggers/L-Analog": "`Shoulder L`", "Classic/Triggers/R-Analog": "`Shoulder R`",
        "Classic/D-Pad/Up": "`Pad N`", "Classic/D-Pad/Down": "`Pad S`",
        "Classic/D-Pad/Left": "`Pad W`", "Classic/D-Pad/Right": "`Pad E`",
        "Classic/Left Stick/Up": "`Left Y+`", "Classic/Left Stick/Down": "`Left Y-`",
        "Classic/Left Stick/Left": "`Left X-`", "Classic/Left Stick/Right": "`Left X+`",
        "Classic/Right Stick/Up": "`Right Y+`", "Classic/Right Stick/Down": "`Right Y-`",
        "Classic/Right Stick/Left": "`Right X-`", "Classic/Right Stick/Right": "`Right X+`",
    },
}

# The Wii Remote's gyroscope, read from the gyro of the DSU server's first pad. Dolphin names that pad
# DSUClient/0/<name>, after the server's name in DSUClient.ini.
GYRO = [f"IMUGyroscope/{axis}" for axis in
        ("Pitch Up", "Pitch Down", "Roll Left", "Roll Right", "Yaw Left", "Yaw Right")]
DSU_NAME = "Handheld"

# A game's gyroscope goes in the name of its profile: "<layout> with gyroscope" or "<layout> without
# gyroscope". GLOBAL stands for the first Wii Remote of WiimoteNew.ini when the game keeps it.
GYRO_ON = " with gyroscope"
GYRO_OFF = " without gyroscope"
GLOBAL = "Global"

# The GameCube pad on the gamepad: A at the bottom, B on the left, as the pads sit.
GCPAD = {
    "Buttons/A": "`Button S`", "Buttons/B": "`Button W`", "Buttons/X": "`Button E`", "Buttons/Y": "`Button N`",
    "Buttons/Z": "`Shoulder R`", "Buttons/Start": "`Start`",
    "Main Stick/Up": "`Left Y+`", "Main Stick/Down": "`Left Y-`",
    "Main Stick/Left": "`Left X-`", "Main Stick/Right": "`Left X+`",
    "C-Stick/Up": "`Right Y+`", "C-Stick/Down": "`Right Y-`", "C-Stick/Left": "`Right X-`", "C-Stick/Right": "`Right X+`",
    "Triggers/L": "`Trigger L`", "Triggers/R": "`Trigger R`",
    "Triggers/L-Analog": "`Trigger L`", "Triggers/R-Analog": "`Trigger R`",
    "D-Pad/Up": "`Pad N`", "D-Pad/Down": "`Pad S`", "D-Pad/Left": "`Pad W`", "D-Pad/Right": "`Pad E`",
}

# The games played with the Wii Remote held sideways, by the first three characters of their id: New
# Super Mario Bros. Wii, Donkey Kong Country Returns, Kirby's Return to Dream Land, Super Paper Mario.
SIDEWAYS_GAMES = {"SMN", "SF8", "SUK", "R8P"}

# Steam describes its virtual gamepads here. SDL names each after the controller it stands for, such
# as "SteamOS Handheld Controller" on the Odin.
STEAM_PADS = os.path.join(".local", "share", "Steam", "config", "virtualgamepadinfo.txt")

SECTION = re.compile(r"\s*\[(.+)\]\s*$")


def read_ini(path):
    """Return the INI's lines, or none when it is missing."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()
    except OSError:
        return []


def ini_get(lines, section, key):
    """Return a key's value in a section, matched without case as Dolphin does, else None."""
    current = None
    for line in lines:
        m = SECTION.match(line)
        if m:
            current = m.group(1).lower()
        elif current == section.lower() and "=" in line:
            k, v = line.split("=", 1)
            if k.strip().lower() == key.lower():
                return v.strip()
    return None


def ini_set(lines, section, key, value):
    """Return the lines with the key set, or removed when value is None. Other lines stay, and a
    section left empty goes."""
    sec, out, current, placed = section.lower(), [], None, value is None
    for line in lines:
        m = SECTION.match(line)
        if m:
            if current == sec and not placed:
                out.append(f"{key} = {value}")
                placed = True
            current = m.group(1).lower()
        elif current == sec and "=" in line and line.split("=", 1)[0].strip().lower() == key.lower():
            continue
        out.append(line)
    if not placed:
        out += [f"{key} = {value}"] if current == sec else [f"[{section}]", f"{key} = {value}"]
    return drop_empty(out, sec)


def drop_empty(lines, sec):
    out, i = [], 0
    while i < len(lines):
        m = SECTION.match(lines[i])
        if m and m.group(1).lower() == sec:
            j = next((j for j in range(i + 1, len(lines)) if SECTION.match(lines[j])), len(lines))
            if not any(line.strip() for line in lines[i + 1:j]):
                i = j
                continue
        out.append(lines[i])
        i += 1
    return out


def section_items(lines, section):
    """Return a section's keys and values, in order."""
    items, current = {}, None
    for line in lines:
        m = SECTION.match(line)
        if m:
            current = m.group(1).lower()
        elif current == section.lower() and "=" in line:
            k, v = line.split("=", 1)
            items[k.strip()] = v.strip()
    return items


def replace_section(lines, section, items):
    """Return the lines with the section's keys replaced by items, at the end."""
    out, skip = [], False
    for line in lines:
        m = SECTION.match(line)
        if m:
            skip = m.group(1).lower() == section.lower()
        if not skip:
            out.append(line)
    return out + [f"[{section}]"] + [f"{k} = {v}" for k, v in items.items()]


def split_profile(name):
    """Return the layout and the gyroscope a profile's name gives, None for each the game keeps."""
    for suffix, gyro in ((GYRO_ON, "true"), (GYRO_OFF, "false")):
        if name and name.endswith(suffix):
            layout = name[:-len(suffix)]
            return (None if layout == GLOBAL else layout), gyro
    return name, None


def profile_name(layout, gyro):
    """Return the profile's name for a layout and a gyroscope, None when the game keeps both."""
    if gyro is None:
        return layout
    return (layout or GLOBAL) + (GYRO_ON if gyro == "true" else GYRO_OFF)


def write_ini(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n" if lines else "")
    os.replace(tmp, path)


class Dolphin:
    def __init__(self, home):
        self.home = home
        # Dolphin keeps ~/.dolphin-emu when it exists, else the XDG folders. The Flatpak keeps its own.
        legacy = os.path.join(home, ".dolphin-emu")
        flatpak = os.path.join(home, ".var", "app", "org.DolphinEmu.dolphin-emu")
        if os.path.isdir(legacy):
            self.config, self.data = os.path.join(legacy, "Config"), legacy
        elif os.path.isdir(os.path.join(flatpak, "config", "dolphin-emu")):
            self.config = os.path.join(flatpak, "config", "dolphin-emu")
            self.data = os.path.join(flatpak, "data", "dolphin-emu")
        else:
            self.config = os.path.join(home, ".config", "dolphin-emu")
            self.data = os.path.join(home, ".local", "share", "dolphin-emu")

    def game_ini(self, game_id):
        return os.path.join(self.data, "GameSettings", f"{game_id}.ini")

    def profile(self, name):
        return os.path.join(self.config, "Profiles", "Wiimote", f"{name}.ini")

    def steam_pad(self):
        """Return Dolphin's name for Steam's first gamepad, such as SDL/0/SteamOS Handheld Controller,
        or None when Steam describes none."""
        name = ini_get(read_ini(os.path.join(self.home, STEAM_PADS)), "slot 0", "name")
        return f"SDL/0/{name}" if name else None

    def dsu_pad(self):
        """Return Dolphin's name for the first pad of the DSU server on dsu.PORT, such as
        DSUClient/0/Handheld, or None when DSUClient.ini lists no such server."""
        lines = read_ini(os.path.join(self.config, "DSUClient.ini"))
        for entry in (ini_get(lines, "Server", "Entries") or "").split(";"):
            parts = entry.split(":")
            if len(parts) >= 3 and parts[1:3] == [dsu.HOST, str(dsu.PORT)]:
                return f"DSUClient/0/{parts[0]}"
        return None

    def gyro(self):
        """Return the gyroscope's keys on the DSU server's first pad, or none without a server."""
        pad = self.dsu_pad()
        return {k: f"`{pad}:Gyro {k.split('/')[1]}`" for k in GYRO} if pad else {}

    def add_dsu(self):
        """Add the DSU server to Dolphin once, when it runs and Dolphin lists none on its address, and
        put the gyroscope on the first Wii Remote unless it has one."""
        if not dsu.running() or self.dsu_pad():
            return
        path = os.path.join(self.config, "DSUClient.ini")
        lines = read_ini(path)
        entries = ini_get(lines, "Server", "Entries") or ""
        lines = ini_set(lines, "Server", "Entries", f"{entries}{DSU_NAME}:{dsu.HOST}:{dsu.PORT};")
        write_ini(path, ini_set(lines, "Server", "Enabled", "True"))
        path = os.path.join(self.config, "WiimoteNew.ini")
        lines = read_ini(path)
        # Without a Device, the section would replace Dolphin's whole default mapping.
        if ini_get(lines, "Wiimote1", "Device") is None or any(ini_get(lines, "Wiimote1", k) for k in GYRO):
            return
        for k, v in self.gyro().items():
            lines = ini_set(lines, "Wiimote1", k, v)
        write_ini(path, lines)

    def setup(self):
        """Give Dolphin the handheld's defaults where it keeps its own: fullscreen, the DSU server
        with the gyroscope, then the first Wii Remote with a Nunchuk and the first GameCube pad on
        Steam's gamepad, while they are still on the keyboard. Values the user set stay. ROM
        Library's profiles get the gyroscope their name gives."""
        path = os.path.join(self.config, "Dolphin.ini")
        lines = read_ini(path)
        if ini_get(lines, "Display", "Fullscreen") is None:
            write_ini(path, ini_set(lines, "Display", "Fullscreen", "True"))
        self.add_dsu()
        pad = self.steam_pad()
        if pad:
            for name, section, layout in (("WiimoteNew.ini", "Wiimote1", {**LAYOUTS[NUNCHUK], **self.gyro()}),
                                          ("GCPadNew.ini", "GCPad1", GCPAD)):
                path = os.path.join(self.config, name)
                lines = read_ini(path)
                if (ini_get(lines, section, "Device") or "XInput2/").startswith("XInput2/"):
                    write_ini(path, replace_section(lines, section, {"Device": pad, **layout}))
        for layout in (None, *LAYOUTS):
            for gyro in (None, "true", "false"):
                name = profile_name(layout, gyro)
                if name and os.path.exists(self.profile(name)):
                    self.save_profile(layout, gyro)

    def save_profile(self, layout, gyro):
        """Write the profile of a layout and a gyroscope. A layout's profile starts from LAYOUTS on the
        first Wii Remote's device and keeps what the user changes in Dolphin. The global layout's
        profile copies the first Wii Remote. The gyroscope is the first Wii Remote's, the DSU
        server's or none."""
        path = self.profile(profile_name(layout, gyro))
        wiimote = read_ini(os.path.join(self.config, "WiimoteNew.ini"))
        old = read_ini(path) if os.path.exists(path) else None
        if layout is None:
            lines = replace_section([], "Profile", section_items(wiimote, "Wiimote1"))
        elif old is not None:
            lines = old
        else:
            device = ini_get(wiimote, "Wiimote1", "Device")
            lines = replace_section([], "Profile", {**({"Device": device} if device else {}), **LAYOUTS[layout]})
        wanted = ({k: ini_get(wiimote, "Wiimote1", k) for k in GYRO} if gyro is None
                  else self.gyro() if gyro == "true" else {})
        for k in GYRO:
            if ini_get(lines, "Profile", k) != wanted.get(k):
                lines = ini_set(lines, "Profile", k, wanted.get(k))
        if lines != old:
            write_ini(path, lines)

    def prepare(self, game_id):
        """Set Dolphin up before a game first runs from a tile or the launcher. A game played sideways
        gets that layout unless it has settings of its own already, even emptied."""
        self.setup()
        if game_id[:3] in SIDEWAYS_GAMES and not os.path.exists(self.game_ini(game_id)):
            self.set(game_id, "wiimote", SIDEWAYS)

    def global_layout(self):
        """Name the first Wii Remote's layout in WiimoteNew.ini after the closest of LAYOUTS."""
        lines = read_ini(os.path.join(self.config, "WiimoteNew.ini"))
        if (ini_get(lines, "Wiimote1", "Options/Sideways Wiimote") or "").lower() == "true":
            return SIDEWAYS
        extension = ini_get(lines, "Wiimote1", "Extension") or "None"
        return {"Nunchuk": NUNCHUK, "Classic": CLASSIC}.get(extension, "Wii Remote")

    def settings(self, game_id):
        """Return the game's values, None where it keeps the global one, and the global values."""
        game = read_ini(self.game_ini(game_id))
        values, globals_ = {}, {}
        for key, (section, name, gfile, gsection, gname, default) in SETTINGS.items():
            values[key] = ini_get(game, section, name)
            if gfile:
                globals_[key] = ini_get(read_ini(os.path.join(self.config, gfile)), gsection, gname) or default
        values["wiimote"], values["gyro"] = split_profile(values["wiimote"])
        globals_["wiimote"] = self.global_layout()
        wiimote = read_ini(os.path.join(self.config, "WiimoteNew.ini"))
        globals_["gyro"] = "true" if any(ini_get(wiimote, "Wiimote1", k) for k in GYRO) else "false"
        return {"id": game_id, "values": values, "globals": globals_}

    def set(self, game_id, key, value):
        """Set one of the game's values, or remove it when value is None. Dolphin gets the handheld's
        defaults first. The layout and the gyroscope make the name of the game's profile."""
        section, name = SETTINGS["wiimote" if key == "gyro" else key][:2]
        self.setup()
        path = self.game_ini(game_id)
        if key in ("wiimote", "gyro"):
            layout, gyro = split_profile(ini_get(read_ini(path), section, name))
            if key == "wiimote":
                layout = value
            elif value in (None, "true", "false"):
                gyro = value
            else:
                raise ValueError(f"unknown gyroscope {value}")
            if layout is not None and layout not in LAYOUTS:
                raise ValueError(f"unknown layout {layout}")
            value = profile_name(layout, gyro)
            if value is not None:
                self.save_profile(layout, gyro)
        write_ini(path, ini_set(read_ini(path), section, name, None if value is None else str(value)))
