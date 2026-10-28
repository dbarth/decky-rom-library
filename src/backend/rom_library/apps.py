"""Non-Steam shortcuts that are not ROM tiles: emulators, front-ends and other apps."""
import os
import re

from .esde import FLATPAK_ID, ENV_ASSIGNMENT, unquote, words

EMULATOR, FRONTEND, OTHER = "emulator", "frontend", "other"
FRONTEND_BINARY = re.compile(r"(?i)(es-de|esde|emulationstation|pegasus-fe|pegasus|retrodeck)([-_. ].*)?(\.appimage)?")
FRONTEND_FLATPAKS = {"org.es_de.frontend", "org.pegasus_frontend.Pegasus", "net.retrodeck.retrodeck"}


def launch_words(options):
    """Return the words of a shortcut's launch options that reach its exe."""
    out = []
    for word in words(options):
        if word == "%command%":
            # Words before %command% wrap the exe; only the ones after reach it.
            out = []
            continue
        out.append(unquote(word))
    return out


def flatpak_app(exe, options):
    """Return the Flatpak id a "flatpak run" shortcut starts, and the words that follow it."""
    if os.path.basename(exe) != "flatpak":
        return None, []
    rest = launch_words(options)
    if "run" not in rest:
        return None, []
    rest = rest[rest.index("run") + 1:]
    while rest and rest[0].startswith("-"):
        rest = rest[1:]
    return (rest[0], rest[1:]) if rest and FLATPAK_ID.fullmatch(rest[0]) else (None, [])


def opens_a_file(args):
    """Tell whether arguments name a file to open, as a game shortcut's do."""
    return any("/" in a for a in args if not ENV_ASSIGNMENT.match(a))


def classify(shortcut, binaries, flatpaks, frontend_binary=None):
    """Return EMULATOR, FRONTEND or OTHER for one shortcut: {exe, launch_options}.

    An emulator shortcut starts the emulator alone: one that opens a game stays OTHER."""
    exe = unquote(shortcut.get("exe") or "")
    options = shortcut.get("launch_options") or ""
    app, after = flatpak_app(exe, options)
    args = after if app else [w for w in launch_words(options) if w and not ENV_ASSIGNMENT.match(w)]
    base = os.path.basename(app or exe)
    if (app in FRONTEND_FLATPAKS or (frontend_binary and exe in (frontend_binary, os.path.realpath(frontend_binary)))
            or FRONTEND_BINARY.fullmatch(base)):
        return FRONTEND
    if opens_a_file(args):
        return OTHER
    if app in flatpaks or exe in binaries or os.path.realpath(exe) in binaries:
        return EMULATOR
    if "/exports/bin/" in exe and FLATPAK_ID.fullmatch(base) and base in flatpaks:
        return EMULATOR
    return OTHER
