"""Eden's settings that ROM Library changes: on a handheld, the question before a game stops, the
window Eden shows while it stops, fullscreen, the update check, the system's language, player 1 on
the gamepad, the gyroscope and the folder of game updates; per game, the settings of Properties."""
import os
import re
import struct
import subprocess

from . import dsu

# Eden's ConfirmStop: 0 Ask_Always, 1 Ask_Based_On_Game, 2 Ask_Never. SIGTERM, which Steam's Exit
# Game and ROM Library's Quit Game send, closes Eden's window, and the window asks first unless the
# value is Ask_Never. Eden handles only the first SIGTERM: a second one kills it. SIGINT makes it
# exit at once, without saving its settings.
ASK_NEVER = "2"
CONFIRM = "confirmStop"

# Eden leaves fullscreen when a game stops (HideFullscreen) and shows its window for about 1 s, as it
# was before the game, with the menu bar and the status bar. Under gamescope, a window smaller than
# the screen shows the game in a corner, and gamescope does not maximize a window.
STATUS_BAR = "showStatusBar"
FULLSCREEN = "fullscreen"
CHECK_FOR_UPDATES = "check_for_updates"

# The folders of updates and DLC that Eden adds to each game, a Qt array in [UI].
CONTENT_DIRS = "Paths\\external_content_dirs"

# Player 1 on Steam's virtual gamepad, which Steam gives the games in game mode. Eden reads its raw
# SDL joystick numbers, in the Xbox 360 driver's order. Each Switch button sits on the gamepad's
# button of the same name: A at the bottom.
PAD = "engine:sdl,guid:03000000de280000ff11000001000000,port:0"
STICK = "offset_x:0.000000,offset_y:0.000000,invert_x:+,invert_y:+,deadzone:0.150000,range:0.950000"
PAD_KEYS = {
    **{f"player_0_button_{name}": f"button:{n}" for n, name in enumerate(
        ("a", "b", "x", "y", "l", "r", "minus", "plus", "home", "lstick", "rstick"))},
    **{f"player_0_button_d{d}": f"hat:0,direction:{d}" for d in ("up", "down", "left", "right")},
    "player_0_button_zl": "axis:2,threshold:0.500000,invert:+",
    "player_0_button_zr": "axis:5,threshold:0.500000,invert:+",
    "player_0_lstick": f"axis_x:0,axis_y:1,{STICK}",
    "player_0_rstick": f"axis_x:3,axis_y:4,{STICK}",
}

# Eden's language_index for a locale's language and territory, else for its language alone.
LANGUAGES = {
    "en_GB": "12", "en_AU": "12", "en_IE": "12", "en_NZ": "12", "fr_CA": "13", "es_ES": "5", "pt_BR": "17",
    "zh_TW": "16", "zh_HK": "16", "en": "1", "fr": "2", "de": "3", "it": "4", "es": "14", "zh": "15", "ko": "7",
    "ja": "0", "nl": "8", "pt": "9", "ru": "10", "pl": "18", "th": "19",
}

# Player 1's motion, read from the DSU server's first pad. Eden names a server by a guid made of its
# address, 127.0.0.1 here (GetHostUUID in udp_client.cpp). Qt quotes a value with a comma.
MOTIONS = ("player_0_motionleft", "player_0_motionright")
DSU_MOTION = f'"engine:cemuhookudp,guid:0000000000000000000000007f000001,motion:0,pad:0,port:{dsu.PORT}"'
# A game's motion, switched off in its own file: Eden then sends the game a still controller.
MOTION = "motion_enabled"

# When a game's file names a profile for player 1, Eden reads all of player 1's keys from that file
# (ReadPlayerValues). ROM Library's profile copies the global keys with A and B swapped, again before
# each start.
PLAYER = "player_0_"
PROFILE = PLAYER + "profile_name"
SWAP_PROFILE = "Swap A and B"
BUTTONS = (PLAYER + "button_a", PLAYER + "button_b")

# The game settings of Properties: Eden's section, key and default on Linux (settings.h). An enum
# is written as its index, such as gpu_accuracy 0 for Low and 1 for High.
SETTINGS = {
    "language": ("System", "language_index", "1"),
    "region": ("System", "region_index", "1"),
    "docked": ("System", "use_docked_mode", "1"),
    "resolution": ("Renderer", "resolution_setup", "3"),
    "accuracy": ("Renderer", "gpu_accuracy", "1"),
    "async_gpu": ("Renderer", "use_asynchronous_gpu_emulation", "true"),
    "async_shaders": ("Renderer", "use_asynchronous_shaders", "false"),
    "reactive_flushing": ("Renderer", "use_reactive_flushing", "true"),
    "anisotropy": ("Renderer", "max_anisotropy", "0"),
    "filter": ("Renderer", "scaling_filter", "0"),
    "gyro": ("Controls", MOTION, "true"),
}

# QWidget::saveGeometry() version 3: a magic number, the version, the frame and normal rectangles,
# the screen number, the maximized and fullscreen flags, the screen's width and the geometry. A
# rectangle is left, top, right and bottom.
GEOMETRY = ">IHH4i4iiBBi4i"
GEOMETRY_MAGIC = 0x1D9D0CB

# Qt's named escapes in an INI value.
ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
HEX = "0123456789abcdefABCDEF"


class Eden:
    def __init__(self, home):
        # The AppImage's config, else the Flatpak's.
        folders = [os.path.join(home, ".config", "eden"),
                   os.path.join(home, ".var", "app", "dev.eden_emu.eden", "config", "eden")]
        self.config = next((f for f in folders if os.path.isdir(f)), folders[0])
        self.ini = os.path.join(self.config, "qt-config.ini")
        self.state = os.path.join(self.config, "window_state.ini")

    def custom(self, game_id):
        return os.path.join(self.config, "custom", f"{game_id}.ini")

    def setup(self, updates=None):
        """Let SIGTERM stop a game without a question, hide the status bar, start in fullscreen, skip
        the update check and take the system's language, unless the user chose a value in Eden. Move
        player 1's buttons from the keyboard to the gamepad, and its motion to the DSU server when it
        runs. Add the folder of updates. Give Eden's window the screen's size. Eden reads its files at
        start and writes them back at exit. Return the files changed."""
        changed = []
        lines = read(self.ini)
        if lines is not None:
            new = lines
            for key, value in ((CONFIRM, ASK_NEVER), (STATUS_BAR, "false"), (FULLSCREEN, "true"),
                               (CHECK_FOR_UPDATES, "false")):
                new = qt_default(new, "UI", key, value)
            language = system_language()
            if language:
                new = qt_default(new, "System", "language_index", language)
            if "engine:keyboard" in qt_value(new, "Controls", BUTTONS[0], "engine:keyboard"):
                for key, value in PAD_KEYS.items():
                    new = qt_set(qt_set(new, "Controls", key + "\\default", "false"), "Controls", key,
                                 f'"{PAD},{value}"')
            if updates:
                new = add_content_dir(new, updates)
            if dsu.running():
                for key in MOTIONS:
                    if "engine:keyboard" in qt_value(new, "Controls", key, "engine:keyboard"):
                        new = qt_set(new, "Controls", key + "\\default", "false")
                        new = qt_set(new, "Controls", key, DSU_MOTION)
            if new != lines:
                write(self.ini, new)
                changed.append(self.ini)
        lines = read(self.state)
        size = screen() if lines is not None else None
        if size:
            value = qt_bytearray(geometry(*size))
            if qt_get(lines, "General", "geometry") != value:
                write(self.state, qt_set(lines, "General", "geometry", value))
                changed.append(self.state)
        return changed

    def settings(self, game_id):
        """Return the game's settings, None for each one it takes from the global settings, and the
        global ones. The global gyroscope is on when motion is on and player 1 reads the DSU server."""
        lines = read(self.ini) or []
        game = read(self.custom(game_id)) or []
        values, globals_ = {}, {}
        for name, (section, key, default) in SETTINGS.items():
            values[name] = None
            if qt_get(game, section, key + "\\use_global") == "false":
                values[name] = qt_value(game, section, key, default)
            globals_[name] = qt_value(lines, section, key, default)
        wired = all("engine:cemuhookudp" in qt_value(lines, "Controls", key, "") for key in MOTIONS)
        globals_["gyro"] = "true" if wired and globals_["gyro"] == "true" else "false"
        values["swap"] = "true" if qt_get(game, "Controls", PROFILE) == SWAP_PROFILE else None
        globals_["swap"] = "false"
        return {"id": game_id, "values": values, "globals": globals_}

    def prepare(self, game_id, updates=None):
        """Give Eden the handheld's defaults, then copy the global buttons again for a game that swaps
        A and B."""
        self.setup(updates)
        if game_id and qt_get(read(self.custom(game_id)) or [], "Controls", PROFILE) == SWAP_PROFILE:
            self.swap(game_id, True)

    def swap(self, game_id, on):
        """Swap A and B in the game's file, from the global keys, or bring back the global ones."""
        path = self.custom(game_id)
        lines = [line for line in read(path) or [] if not line.startswith(PLAYER)]
        if on:
            keys = dict(line.split("=", 1) for line in section_lines(read(self.ini) or [], "Controls")
                        if line.startswith(PLAYER) and "=" in line)
            if not all(keys.get(key) for key in BUTTONS):
                raise ValueError("Eden has no A and B buttons for player 1")
            a, b = BUTTONS
            keys.update({PROFILE + "\\default": "false", PROFILE: SWAP_PROFILE, a + "\\default": "false",
                         a: keys[b], b + "\\default": "false", b: keys[a]})
            # qt_set puts a new key first in its section.
            for key, value in reversed(keys.items()):
                lines = qt_set(lines, "Controls", key, value)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, lines)

    def set(self, game_id, name, value):
        """Set one of the game's settings, or bring back the global value with None. Eden gets the
        handheld's defaults first."""
        if name == "swap" and value in ("true", "false", None):
            self.setup()
            return self.swap(game_id, value == "true")
        section, key, default = SETTINGS.get(name, (None, None, ""))
        boolean = default in ("true", "false")
        if not key or value is not None and not (value in ("true", "false") if boolean else value.isdigit()):
            raise ValueError(f"no Eden setting {name}={value}")
        self.setup()
        path = self.custom(game_id)
        lines = read(path) or []
        if value is None:
            for k in (key + "\\default", key):
                lines = qt_set(lines, section, k, None)
            lines = qt_set(lines, section, key + "\\use_global", "true")
        else:
            lines = qt_set(lines, section, key, value)
            lines = qt_set(lines, section, key + "\\default", "true" if value == default else "false")
            lines = qt_set(lines, section, key + "\\use_global", "false")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, lines)


def system_language():
    """Return Eden's language_index for the system's locale, such as 2 for fr_FR.UTF-8, else None.
    Decky's service may run without LANG: /etc/locale.conf holds the system's."""
    value = next((os.environ[v] for v in ("LC_ALL", "LC_MESSAGES", "LANG") if os.environ.get(v)), "")
    if value in ("", "C", "POSIX") or value.startswith("C."):
        try:
            with open("/etc/locale.conf", encoding="utf-8") as f:
                value = next((line.split("=", 1)[1].strip().strip('"') for line in f
                              if line.startswith("LANG=")), "")
        except OSError:
            return None
    locale = value.split(".")[0].split("@")[0]
    return LANGUAGES.get(locale) or LANGUAGES.get(locale.split("_")[0])


def add_content_dir(lines, path):
    """Return the lines with a folder added to Eden's external content folders, once."""
    size = int(qt_get(lines, "UI", CONTENT_DIRS + "\\size") or 0)
    if path in (qt_get(lines, "UI", f"{CONTENT_DIRS}\\{i}\\path") for i in range(1, size + 1)):
        return lines
    lines = qt_set(lines, "UI", f"{CONTENT_DIRS}\\{size + 1}\\path", path)
    return qt_set(lines, "UI", CONTENT_DIRS + "\\size", str(size + 1))


def screen():
    """Return the width and height of gamescope's X screen, else None."""
    try:
        out = subprocess.run(["xwininfo", "-root"], env={**os.environ, "DISPLAY": ":0"},
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    width, height = re.search(r"Width: (\d+)", out), re.search(r"Height: (\d+)", out)
    return (int(width[1]), int(height[1])) if width and height else None


def geometry(width, height):
    """Return a saved geometry for a maximized window that covers the screen."""
    rect = (0, 0, width - 1, height - 1)
    return struct.pack(GEOMETRY, GEOMETRY_MAGIC, 3, 0, *rect, *rect, 0, 1, 0, width, *rect)


def read(path):
    """Return the lines of a file, else None when it does not exist."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return None


def write(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


def qt_default(lines, section, key, value):
    """Return the lines with the key set to the value, unless the user chose one: Eden marks a value
    it did not choose with key\\default=true."""
    if qt_get(lines, section, key + "\\default") not in (None, "true"):
        return lines
    return qt_set(qt_set(lines, section, key + "\\default", "false"), section, key, value)


def qt_value(lines, section, key, default):
    """Return a key's value as Eden reads it: its default unless key\\default is false."""
    if qt_get(lines, section, key + "\\default") != "false":
        return default
    return qt_get(lines, section, key) or default


def section_lines(lines, section):
    """Return the lines of a section in a Qt INI file."""
    out, current = [], None
    for line in lines:
        if line.startswith("["):
            current = line.strip()[1:-1]
        elif current == section:
            out.append(line)
    return out


def qt_get(lines, section, key):
    """Return a key's value in a section of a Qt INI file, else None. Qt matches keys with case."""
    current = None
    for line in lines:
        if line.startswith("["):
            current = line.strip()[1:-1]
        elif current == section and line.split("=", 1)[0] == key:
            return line.split("=", 1)[1]
    return None


def qt_set(lines, section, key, value):
    """Return the lines with the key set in place, as Qt writes it: key=value without spaces, or
    removed when value is None. A new key goes first in its section."""
    out, current, placed = [], None, value is None
    for line in lines:
        if line.startswith("["):
            current = line.strip()[1:-1]
            out.append(line)
            if current == section and value is not None and qt_get(lines, section, key) is None:
                out.append(f"{key}={value}")
                placed = True
        elif current == section and line.split("=", 1)[0] == key:
            if value is not None:
                out.append(f"{key}={value}")
            placed = True
        else:
            out.append(line)
    if not placed:
        out += [f"[{section}]", f"{key}={value}"]
    return out


def qt_bytes(value):
    """Return the bytes of an @ByteArray(...) value in a Qt INI file, else None. Qt reads \\x and \\0
    escapes with as many digits as follow, and drops quotes."""
    out, i = [], 0
    while i < len(value):
        c = value[i]
        i += 1
        if c == '"':
            continue
        if c != "\\" or i == len(value):
            out.append(c)
            continue
        c = value[i]
        i += 1
        if c == "x" or c in "01234567":
            base, digits, n = (16, HEX, 0) if c == "x" else (8, "01234567", int(c))
            while i < len(value) and value[i] in digits:
                n = n * base + int(value[i], 16)
                i += 1
            out.append(chr(n))
        else:
            out.append(ESCAPES.get(c, c))
    text = "".join(out)
    if not text.startswith("@ByteArray(") or not text.endswith(")"):
        return None
    try:
        return text[11:-1].encode("latin-1")
    except UnicodeEncodeError:
        return None


def qt_bytearray(data):
    """Return bytes as QSettings writes an @ByteArray in an INI file. A hex digit after a \\x or \\0
    escape is escaped too, and a value with ; , or = goes in quotes."""
    out, escape_digit, quote = [], False, False
    for c in "@ByteArray(" + data.decode("latin-1") + ")":
        n = ord(c)
        quote = quote or c in ";,="
        if escape_digit and c in HEX:
            out.append(f"\\x{n:x}")
            continue
        escape_digit = False
        named = next((k for k, v in ESCAPES.items() if v == c), None)
        if c == "\0":
            out.append("\\0")
            escape_digit = True
        elif named:
            out.append("\\" + named)
        elif c in '"\\':
            out.append("\\" + c)
        elif n <= 0x1f or n >= 0x7f:
            out.append(f"\\x{n:x}")
            escape_digit = True
        else:
            out.append(c)
    text = "".join(out)
    return f'"{text}"' if quote else text
