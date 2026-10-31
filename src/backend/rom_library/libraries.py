"""Finds the ROM folders of the tools, the home and the drives, and links several into one library."""
import glob
import os
import re

from .esde import Unresolved
from .jsonfile import read_json

# ES-DE keeps ROMs in ~/ROMs by default, EmuDeck and Loadout in ~/Emulation/roms, RetroDECK in
# ~/retrodeck/roms.
HOME_DIRS = ("~/ROMs", "~/Emulation/roms", "~/retrodeck/roms")
# On a card or a drive, EmuDeck and Loadout use Emulation/roms, RetroDECK retrodeck/roms, Android ROMs,
# and ROCKNIX, Knulli and Batocera roms.
DRIVE_DIRS = ("Emulation/roms", "retrodeck/roms", "ROMs", "roms")
# udisks mounts a drive at /run/media/<user>/<label>, and SteamOS before 3.5 at /run/media/<device>.
MEDIA = "/run/media"
MOUNTS = "/proc/self/mounts"
SYS_BLOCK = "/sys/class/block"
# An installed Loadout keeps the games in ~/Emulation when its settings name no library.
HUB = "/usr/lib/steamos-arm/hub/hub.py"
# These file systems hold no symbolic links. fuseblk is NTFS through ntfs-3g.
NO_LINKS = ("exfat", "vfat", "msdos", "ntfs", "ntfs3", "fuseblk")
# A new library goes in Loadout's and EmuDeck's folder on its drive.
NEW_DIR = "Emulation/roms"
# ES-DE and EmuDeck put these files in each system's folder. Both write them again after a delete.
PLACEHOLDERS = ("systeminfo.txt", "metadata.txt")
EMULATOR = re.compile(r"%EMULATOR_([^%]+)%")
# ES-DE runs shortcuts and scripts through this emulator. A new library makes no folder for their systems.
SHELL = "OS-SHELL"
# The libraries page shows these names, and ES-DE's full name for the other systems.
SHORT_NAMES = {
    "3do": "3DO", "amiga": "Amiga", "amstradcpc": "Amstrad CPC", "arcade": "Arcade", "atari2600": "Atari 2600",
    "atari5200": "Atari 5200", "atari7800": "Atari 7800", "atarijaguar": "Jaguar", "atarilynx": "Lynx",
    "atarist": "Atari ST", "atomiswave": "Atomiswave", "c64": "C64", "colecovision": "ColecoVision",
    "cps1": "CPS-1", "cps2": "CPS-2", "cps3": "CPS-3", "dos": "DOS", "dreamcast": "Dreamcast",
    "famicom": "Famicom", "fbneo": "Arcade", "fds": "Famicom Disk", "gamegear": "Game Gear", "gb": "Game Boy",
    "gba": "GBA", "gbc": "Game Boy Color", "gc": "GameCube", "genesis": "Genesis", "mame": "MAME",
    "mastersystem": "Master System", "megacd": "Mega-CD", "megadrive": "Mega Drive", "model2": "Model 2",
    "model3": "Model 3", "msx": "MSX", "n3ds": "3DS", "n64": "N64", "naomi": "NAOMI", "nds": "DS",
    "neogeo": "Neo Geo", "neogeocd": "Neo Geo CD", "nes": "NES", "ngp": "Neo Geo Pocket", "ngpc": "NGP Color",
    "pcengine": "PC Engine", "pcenginecd": "PC Engine CD", "pico8": "PICO-8", "pokemini": "Pokémon Mini",
    "ports": "Ports", "ps2": "PS2", "ps3": "PS3", "psp": "PSP", "psvita": "PS Vita", "psx": "PlayStation",
    "saturn": "Saturn", "scummvm": "ScummVM", "sega32x": "32X", "segacd": "Sega CD", "sfc": "Super Famicom",
    "sg-1000": "SG-1000", "snes": "SNES", "snesna": "SNES", "switch": "Switch", "tg16": "TurboGrafx-16",
    "tg-cd": "TurboGrafx-CD", "vectrex": "Vectrex", "virtualboy": "Virtual Boy", "wii": "Wii", "wiiu": "Wii U",
    "wonderswan": "WonderSwan", "wonderswancolor": "WonderSwan Color", "x68000": "X68000", "xbox": "Xbox",
    "zxspectrum": "ZX Spectrum",
}


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def shell_value(path, name):
    """Return a variable's value in a shell or ini file, without its quotes, else None."""
    m = re.search(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=\s*(.*?)\s*$", read_text(path), re.MULTILINE)
    return m and m[1].strip("\"'") or None


def mounts():
    """Return [(mount point, device, file system)], the longest mount point first. The kernel writes
    a space in a path as \\040."""
    out = []
    for line in read_text(MOUNTS).splitlines():
        fields = line.split()
        if len(fields) >= 3:
            point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields[1])
            out.append((point, fields[0], fields[2]))
    return sorted(out, key=lambda m: len(m[0]), reverse=True)


def existing(path):
    """Return the path, or its nearest folder that exists."""
    while not os.path.exists(path) and os.path.dirname(path) != path:
        path = os.path.dirname(path)
    return path


def mount_of(path, table):
    real = os.path.realpath(existing(path))
    return next((m for m in table if real == m[0] or real.startswith(m[0].rstrip("/") + "/")), ("/", "", ""))


def drive_kind(device):
    """Return "sd", "usb" or "internal" for a block device. A partition's folder in /sys sits inside
    its disk's. An mmcblk disk of type MMC is eMMC, on the board. The other mmcblk disks are cards."""
    folder = os.path.realpath(os.path.join(SYS_BLOCK, os.path.basename(os.path.realpath(device))))
    if not os.path.exists(folder):
        return "internal"
    disk = os.path.dirname(folder) if os.path.exists(os.path.join(folder, "partition")) else folder
    if os.path.basename(disk).startswith("mmcblk"):
        return "internal" if read_text(os.path.join(disk, "device", "type")).strip() == "MMC" else "sd"
    return "usb" if "/usb" in disk else "internal"


def drive(point, device):
    """Return the drive's kind and its name in Steam's words: Internal Storage, MicroSD Card, else the
    label udisks mounts it under."""
    kind = drive_kind(device)
    if kind == "internal":
        return {"kind": kind, "name": "Internal Storage"}
    if kind == "sd":
        return {"kind": kind, "name": "MicroSD Card"}
    return {"kind": kind, "name": os.path.basename(point) if point.startswith(MEDIA + "/") else "USB Drive"}


def is_placeholder(folder):
    """Tell whether a system's folder is empty or holds ES-DE's and EmuDeck's files alone. A link is
    no placeholder."""
    if os.path.islink(folder):
        return False
    try:
        with os.scandir(folder) as entries:
            return all(e.name in PLACEHOLDERS and e.is_file(follow_symlinks=False) for e in entries)
    except OSError:
        return False


def exact_dir(base, rel):
    """Return base/rel when each part of rel is a folder of that exact name. exFAT also finds roms under
    the name ROMs."""
    path = base
    for part in rel.split("/"):
        try:
            if part not in os.listdir(path):
                return None
        except OSError:
            return None
        path = os.path.join(path, part)
    return path if os.path.isdir(path) else None


def inode(path):
    try:
        st = os.stat(path)
        return st.st_dev, st.st_ino
    except OSError:
        return None


class Libraries:
    def __init__(self, home, esde):
        self.home = home
        self.esde = esde

    def expand(self, path):
        return self.home + path[1:] if path.startswith("~") else path

    def tools(self):
        """Return {tool: ROM folder} for the tools whose settings name one."""
        out = {}
        if os.path.isfile(os.path.join(self.esde.esde_home, "settings", "es_settings.xml")):
            out["ES-DE"] = self.expand(self.esde.setting("ROMDirectory") or "~/ROMs")
        hub = read_json(os.path.join(self.home, ".config", "steamos-arm", "hub.json"), {})
        library = hub.get("library") if isinstance(hub, dict) else None
        if isinstance(library, str) and library.startswith(("/", "~")):
            out["Loadout"] = os.path.join(self.expand(library), "roms")
        elif os.path.isfile(HUB):
            out["Loadout"] = os.path.join(self.home, "Emulation", "roms")
        emudeck = shell_value(os.path.join(self.home, ".config", "EmuDeck", "settings.sh"), "romsPath")
        if emudeck:
            out["EmuDeck"] = self.expand(emudeck)
        retrodeck = shell_value(os.path.join(
            self.home, ".var", "app", "net.retrodeck.retrodeck", "config", "retrodeck", "retrodeck.cfg"), "roms_folder")
        if retrodeck:
            out["RetroDECK"] = self.expand(retrodeck)
        return {tool: os.path.normpath(path) for tool, path in out.items()}

    def places(self):
        """Return the folders to check, the tools' first, each once. The SteamOS ARM port links
        /run/media/<label> to the mount point: the scan skips the links."""
        points = [p for p in sorted(glob.glob(os.path.join(MEDIA, "*")) + glob.glob(os.path.join(MEDIA, "*", "*")))
                  if not os.path.islink(p)]
        drives = [exact_dir(p, d) for d in DRIVE_DIRS for p in points]
        found, seen = [], set()
        for path in [*self.tools().values(), *(self.expand(d) for d in HOME_DIRS), *drives]:
            key = path and os.path.isdir(path) and inode(path)
            if key and key not in seen:
                seen.add(key)
                found.append(path)
        return found

    def system_folder(self, system, root):
        return os.path.normpath(system["path"].replace("%ROMPATH%", root))

    def find(self):
        """Return the folders that hold games, as Library in tiles.ts. A system's folder counts when it
        holds a file with the system's extensions. A system's folder that links into another place
        counts in that place alone."""
        systems = self.esde.systems()
        places = self.places()
        reals = [os.path.realpath(p) for p in places]
        tools = self.tools()
        table = mounts()
        out = []
        for i, root in enumerate(places):
            counted = []
            for sid, s in systems.items():
                folder = self.system_folder(s, root)
                if not os.path.isdir(folder):
                    continue
                real = os.path.realpath(folder)
                if os.path.islink(folder) and any(j != i and (real + "/").startswith(r + "/") for j, r in enumerate(reals)):
                    continue
                games = len(self.esde.scan(s, [folder]))
                if games:
                    counted.append({"id": sid, "name": SHORT_NAMES.get(sid, s["fullname"]), "games": games})
            if not counted:
                continue
            point, device, fs = mount_of(root, table)
            out.append({
                "path": root,
                "where": self.where(root, point),
                "drive": drive(point, device),
                "fs": fs,
                "links": fs not in NO_LINKS,
                "usedBy": [t for t, p in tools.items() if os.path.realpath(p) == reals[i]],
                "games": sum(s["games"] for s in counted),
                "systems": sorted(counted, key=lambda s: -s["games"]),
            })
        return out

    def where(self, path, point):
        """Return the path from the home, such as ~/Emulation/roms, or from the drive's label, such as
        MicroSD/Emulation/roms."""
        if path == self.home or path.startswith(self.home + "/"):
            return "~" + path[len(self.home):]
        if point.startswith(MEDIA + "/"):
            rel = os.path.relpath(os.path.realpath(path), point)
            return os.path.normpath(os.path.join(os.path.basename(point), rel))
        return path

    def installed(self, system):
        """Tell whether one of a system's commands names an emulator that is installed."""
        for _, command in system["commands"]:
            m = EMULATOR.search(command)
            if not m or m[1] == SHELL:
                continue
            try:
                self.esde.check(command)
                return True
            except (Unresolved, OSError):
                pass
        return False

    def new_places(self):
        """Return where a new library can go: ~/Emulation/roms, then Emulation/roms on each card or drive
        that holds links. Each place gives its drive's free bytes. A system with an emulator installed
        gets a folder."""
        systems = sorted(({"id": sid, "name": SHORT_NAMES.get(sid, s["fullname"])}
                          for sid, s in self.esde.systems().items() if self.installed(s)),
                         key=lambda s: s["name"].lower())
        table = mounts()
        paths = [os.path.join(self.home, NEW_DIR)]
        for point, _, fs in sorted(table):
            path = os.path.join(point, NEW_DIR)
            if point.startswith(MEDIA + "/") and fs not in NO_LINKS and path not in paths:
                paths.append(path)
        out = []
        for path in paths:
            point, device, _ = mount_of(path, table)
            try:
                st = os.statvfs(existing(path))
                free = st.f_bavail * st.f_frsize
            except OSError:
                continue
            out.append({"path": path, "drive": drive(point, device), "free": free, "systems": systems})
        return out

    def link(self, main, include):
        """Link each included system that the main folder lacks or holds empty. Return the links made."""
        made = []
        for sid, s in self.esde.systems().items():
            target = self.system_folder(s, main)
            for root in include:
                folder = self.system_folder(s, root)
                if not os.path.isdir(folder) or not self.esde.scan(s, [folder]):
                    continue
                if os.path.lexists(target) and not is_placeholder(target):
                    break
                if os.path.isdir(target):
                    for name in PLACEHOLDERS:
                        if os.path.lexists(os.path.join(target, name)):
                            os.remove(os.path.join(target, name))
                    os.rmdir(target)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                os.symlink(folder, target)
                made.append(target)
                break
        return made

    def create(self, path, include):
        """Link the included systems into a new library, then make a folder for each other system with
        an emulator installed."""
        made = self.link(path, include)
        place = next((p for p in self.new_places() if p["path"] == path), None)
        systems = self.esde.systems()
        for s in place["systems"] if place else []:
            os.makedirs(self.system_folder(systems[s["id"]], path), exist_ok=True)
        return made
