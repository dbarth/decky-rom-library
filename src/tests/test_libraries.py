"""Tests for the ROM folders the scan finds and the libraries made of them. Run with:
python3 -I tests/test_libraries.py"""
import json
import logging
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, HERE)

from rom_library import esde, libraries, library, picks  # noqa: E402
from test_esde import ARM_FILES, Home, touch  # noqa: E402

DEFAULTS = os.path.join(HERE, "..", "backend", "defaults")


class LibrariesTest(unittest.TestCase):
    """Each test runs on the Odin's home, an exFAT card, an exFAT USB drive and an ext4 LUN."""

    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.cleanup)
        # The kernel's mount table holds real paths: macOS puts the temporary folders under /private.
        root = os.path.realpath(self.h.root)
        media = os.path.join(root, "run/media")
        self.card = os.path.join(media, "steamos/MicroSD")
        self.usb = os.path.join(media, "steamos/GAMES")
        self.ext4 = os.path.join(media, "steamos/LUN7")
        sys_block = os.path.join(root, "sys/class/block")
        devices = os.path.join(root, "sys/devices")
        for disk, part in (("platform/ufs/sda", "sda8"), ("platform/mmc/mmcblk0", "mmcblk0p1"),
                           ("platform/xhci/usb1/1-1/sdb", "sdb1"), ("platform/ufs/sdh", "sdh1")):
            touch(os.path.join(devices, disk, part, "partition"), "1")
            os.makedirs(sys_block, exist_ok=True)
            os.symlink(os.path.join(devices, disk, part), os.path.join(sys_block, part))
        touch(os.path.join(devices, "platform/mmc/mmcblk0/device/type"), "SD\n")
        mounts = os.path.join(root, "mounts")
        touch(mounts, f"/dev/sda8 / ext4 rw 0 0\n/dev/mmcblk0p1 {self.card} exfat rw 0 0\n"
                      f"/dev/sdb1 {self.usb} exfat rw 0 0\n/dev/sdh1 {self.ext4} ext4 rw 0 0\n")
        for name, value in (("MEDIA", media), ("MOUNTS", mounts), ("SYS_BLOCK", sys_block),
                            ("HUB", os.path.join(root, "hub.py"))):
            self.addCleanup(setattr, libraries, name, getattr(libraries, name))
            setattr(libraries, name, value)
        self.addCleanup(setattr, esde, "CARD_ROM_DIRS", esde.CARD_ROM_DIRS)
        esde.CARD_ROM_DIRS = (os.path.join(media, "*/*/Emulation/roms"),)
        self.sd = os.path.join(self.card, "Emulation/roms")
        for rel, size in (("snes/Super Metroid.sfc", 300), ("snes/Zelda.sfc", 200), ("gba/Metroid Fusion.gba", 80),
                          ("psp/LittleBigPlanet (Europe) (PSP) (PSN).iso", 0), ("psp/Patapon.iso", 50)):
            touch(os.path.join(self.sd, rel), "x" * size)
        self.games = os.path.join(self.usb, "roms")
        touch(os.path.join(self.games, "nes/Mario.nes"), "x")
        self.settings = os.path.join(root, "settings")
        self.lib = library.Library(DEFAULTS, self.settings, self.h.home, os.path.join(root, "runtime"),
                                   logging.getLogger())
        self.lib.esde.bundled = lambda: ARM_FILES

    def found(self):
        return {f["path"]: f for f in self.lib.find_libraries()}

    def test_find_names_each_folder_its_drive_and_systems(self):
        found = self.found()
        self.assertEqual(sorted(found), sorted([self.h.roms, self.sd, self.games]))
        home, sd, usb = found[self.h.roms], found[self.sd], found[self.games]
        self.assertEqual((home["where"], home["drive"], home["fs"], home["links"], home["usedBy"]),
                         ("~/ROMs", {"kind": "internal", "name": "Internal Storage"}, "ext4", True, ["ES-DE"]))
        self.assertEqual((sd["where"], sd["drive"], sd["fs"], sd["links"], sd["usedBy"]),
                         ("MicroSD/Emulation/roms", {"kind": "sd", "name": "MicroSD Card"}, "exfat", False, []))
        self.assertEqual(sd["systems"], [{"id": "psp", "name": "PSP", "games": 2},
                                         {"id": "snes", "name": "SNES", "games": 2},
                                         {"id": "gba", "name": "GBA", "games": 1}])
        self.assertEqual(sd["games"], 5)
        self.assertEqual((usb["where"], usb["drive"]), ("GAMES/roms", {"kind": "usb", "name": "GAMES"}))

    def test_an_emmc_disk_is_internal_storage(self):
        touch(os.path.join(self.h.root, "sys/devices/platform/mmc/mmcblk0/device/type"), "MMC\n")
        self.assertEqual(self.found()[self.sd]["drive"], {"kind": "internal", "name": "Internal Storage"})

    def test_tools_name_their_folders(self):
        touch(os.path.join(self.h.home, ".config/steamos-arm/hub.json"),
              json.dumps({"library": os.path.join(self.card, "Emulation")}))
        touch(os.path.join(self.h.home, ".config/EmuDeck/settings.sh"), f'romsPath="{self.games}"\n')
        self.assertEqual(self.found()[self.sd]["usedBy"], ["Loadout"])
        self.assertEqual(self.found()[self.games]["usedBy"], ["EmuDeck"])
        # Loadout keeps the games in ~/Emulation when hub.json names no library.
        os.remove(os.path.join(self.h.home, ".config/steamos-arm/hub.json"))
        touch(libraries.HUB)
        touch(os.path.join(self.h.home, "Emulation/roms/n64/Mario.z64"))
        self.assertEqual(self.found()[os.path.join(self.h.home, "Emulation/roms")]["usedBy"], ["Loadout"])

    def test_a_system_linked_into_another_folder_counts_there(self):
        os.symlink(os.path.join(self.sd, "gba"), self.h.rom("gba"))
        home = self.found()[self.h.roms]
        self.assertNotIn("gba", [s["id"] for s in home["systems"]])

    def test_new_places_hold_links_and_get_the_installed_systems(self):
        places = self.lib.new_libraries()
        self.assertEqual([p["path"] for p in places],
                         [os.path.join(self.h.home, "Emulation/roms"), os.path.join(self.ext4, "Emulation/roms")])
        self.assertEqual(places[0]["drive"]["name"], "Internal Storage")
        self.assertGreater(places[0]["free"], 0)
        ids = {s["id"] for s in places[0]["systems"]}
        self.assertTrue({"fbneo", "n64", "psp", "switch", "wii"} <= ids)
        self.assertFalse({"desktop", "ports", "snes"} & ids)

    def test_use_reads_one_folder_and_points_esde_at_it(self):
        self.lib.use_library(self.sd)
        self.assertEqual(self.lib.esde.rom_dirs(), [self.sd + "/"])
        self.assertEqual(self.lib.esde.setting("ROMDirectory"), self.sd)
        self.assertEqual([g["name"] for g in self.lib.games("psp")], ["LittleBigPlanet", "Patapon"])
        self.assertNotIn("fbneo", self.lib.systems())

    def test_combine_links_the_missing_systems_and_keeps_their_paths(self):
        # ES-DE made an empty folder for the Game Boy Advance.
        touch(self.h.rom("gba/systeminfo.txt"), "Game Boy Advance")
        self.lib.combine_libraries(self.h.roms, [self.sd, self.games])
        self.assertEqual(self.lib.roots(), [self.h.roms, self.sd, self.games])
        self.assertEqual(self.lib.esde.setting("ROMDirectory"), self.h.roms)
        for sid, root in (("gba", self.sd), ("snes", self.sd), ("nes", self.games)):
            self.assertEqual(os.readlink(self.h.rom(sid)), os.path.join(root, sid))
        # ROM Library reads the card's PSP games through the roots. The main folder keeps its own.
        self.assertFalse(os.path.islink(self.h.rom("psp")))
        systems = self.lib.systems()
        self.assertEqual(systems["snes"]["roots"], [os.path.join(self.sd, "snes")])
        self.assertEqual(systems["psp"]["roots"], [self.h.rom("psp"), os.path.join(self.sd, "psp")])
        # The card's copy of LittleBigPlanet repeats the main folder's.
        self.assertEqual([g["path"] for g in self.lib.games("psp")],
                         [self.h.rom("psp/LittleBigPlanet (Europe) (PSP) (PSN).iso"), os.path.join(self.sd, "psp/Patapon.iso")])
        self.lib.combine_libraries(self.h.roms, [self.sd, self.games])
        self.assertEqual(os.readlink(self.h.rom("gba")), os.path.join(self.sd, "gba"))

    def test_a_copy_in_another_system_counts_once(self):
        touch(self.h.rom("snes/Zelda.sfc"), "x" * 200)
        touch(self.h.rom("sfc/Super Metroid.sfc"), "x" * 300)
        touch(self.h.rom("sfc/Zelda.sfc"), "x" * 199)
        self.lib.combine_libraries(self.h.roms, [self.sd])
        self.assertEqual([g["path"] for g in self.lib.games("snes")], [self.h.rom("snes/Zelda.sfc")])
        self.assertEqual(self.lib.systems()["snes"]["roots"], [self.h.rom("snes"), os.path.join(self.sd, "snes")])
        # A copy with a tile stays listed: the user can remove the tile.
        self.lib.tiles[os.path.join(self.sd, "snes/Zelda.sfc")] = {"appid": 1, "system": "snes"}
        self.assertEqual(len(self.lib.games("snes")), 2)

    def test_create_makes_a_main_library_for_exfat_folders(self):
        main = os.path.join(self.h.home, "Emulation/roms")
        self.lib.create_library(main, [self.sd, self.games])
        self.assertEqual(os.readlink(os.path.join(main, "snes")), os.path.join(self.sd, "snes"))
        self.assertTrue(os.path.isdir(os.path.join(main, "switch")))
        self.assertEqual(self.lib.roots(), [main, self.sd, self.games])
        self.assertEqual(self.lib.esde.setting("ROMDirectory"), main)
        self.assertEqual([g["path"] for g in self.lib.games("snes")],
                         [os.path.join(self.sd, "snes", f) for f in ("Super Metroid.sfc", "Zelda.sfc")])

    def test_batocera_folders_count_and_link_under_esde_names(self):
        batocera = os.path.join(self.usb, "roms")
        touch(os.path.join(batocera, "gamecube/Wind Waker.rvz"), "x")
        touch(os.path.join(batocera, "tic-80/Tiny.tic"), "x")
        found = self.found()[batocera]
        self.assertEqual(sorted(s["id"] for s in found["systems"]), ["gc", "nes", "tic80"])
        self.lib.combine_libraries(self.h.roms, [batocera])
        self.assertEqual(os.readlink(self.h.rom("gc")), os.path.join(batocera, "gamecube"))
        self.assertEqual(os.readlink(self.h.rom("tic80")), os.path.join(batocera, "tic-80"))
        self.assertEqual(self.lib.systems()["gc"]["roots"], [os.path.join(batocera, "gamecube")])
        self.assertEqual([g["path"] for g in self.lib.games("gc")], [os.path.join(batocera, "gamecube/Wind Waker.rvz")])

    def test_a_tile_follows_its_game_to_the_new_main_folder(self):
        applied = {"name": "", "exe": "", "start_dir": "", "launch_options": ""}
        zelda, metroid = os.path.join(self.sd, "snes/Zelda.sfc"), os.path.join(self.sd, "snes/Super Metroid.sfc")
        fusion = os.path.join(self.sd, "gba/Metroid Fusion.gba")
        self.lib.record(zelda, 1, "snes", applied)
        self.lib.record(metroid, 2, "snes", applied)
        self.lib.record(fusion, 3, "gba", applied)
        self.lib.choose(zelda, "portrait", "file:/art/zelda.png")
        # The internal storage holds a copy of Zelda, and a Super Metroid of another size.
        touch(self.h.rom("snes/Zelda.sfc"), "x" * 200)
        touch(self.h.rom("snes/Super Metroid.sfc"), "x" * 299)
        self.lib.use_library(self.h.roms)
        self.assertEqual(self.lib.tiles[self.h.rom("snes/Zelda.sfc")]["appid"], 1)
        self.assertEqual(self.lib.choice(self.h.rom("snes/Zelda.sfc"), "portrait"), "file:/art/zelda.png")
        self.assertIsNone(self.lib.choice(zelda, "portrait"))
        self.assertEqual(sorted(p for p, tile in self.lib.tiles.items() if tile["appid"] != 1), sorted([metroid, fusion]))
        games = {g["path"]: g for g in self.lib.games("snes")}
        self.assertFalse(games[self.h.rom("snes/Zelda.sfc")]["missing"])
        self.assertTrue(games[metroid]["missing"])
        # The move lasts: a new library object reads it from tiles.json.
        self.assertIn(self.h.rom("snes/Zelda.sfc"), library.Library(
            DEFAULTS, self.settings, self.h.home, os.path.join(self.h.root, "runtime"), logging.getLogger()).tiles)

    def mount(self, label):
        """Mount the card under another label."""
        card = os.path.join(os.path.dirname(self.card), label)
        os.rename(self.card, card)
        mounts = os.path.join(os.path.realpath(self.h.root), "mounts")
        with open(mounts) as f:
            table = f.read()
        touch(mounts, table.replace(f" {self.card} ", f" {card} "))
        self.card, self.sd = card, os.path.join(card, "Emulation/roms")

    def library_file(self, root):
        with open(os.path.join(root, picks.FILE)) as f:
            return json.load(f)

    def test_picks_live_in_the_library_of_their_game(self):
        self.lib.combine_libraries(self.h.roms, [self.sd])
        zelda = os.path.join(self.sd, "snes/Zelda.sfc")
        self.lib.choose(zelda, "portrait", "sgdb:1")
        self.lib.set_vulkan_driver(zelda, "mesa-26.3")
        self.lib.choose("app:12", "hero", "sgdb:2")
        self.assertEqual(self.library_file(self.sd)["games"],
                         {"snes/Zelda.sfc": {"art": {"portrait": "sgdb:1"}, "driver": "mesa-26.3"}})
        # An app is in no library: the plugin keeps its picks.
        self.assertEqual(self.lib.picks.art, {"app:12": {"hero": "sgdb:2"}})
        self.assertEqual(self.lib.vulkan_driver(zelda)["driver"], "mesa-26.3")
        self.lib.set_vulkan_driver(zelda, None)
        self.lib.choose(zelda, "portrait", None)
        self.assertEqual(self.library_file(self.sd)["games"], {})

    def test_the_plugin_moves_its_picks_into_the_libraries(self):
        zelda, gone = os.path.join(self.sd, "snes/Zelda.sfc"), os.path.join(self.sd, "snes/Gone.sfc")
        touch(os.path.join(self.settings, "settings.json"), json.dumps({"roots": [self.h.roms, self.sd]}))
        touch(os.path.join(self.settings, "art.json"), json.dumps(
            {zelda: {"portrait": "sgdb:1"}, gone: {"portrait": "sgdb:3"}, "app:12": {"hero": "sgdb:2"}}))
        touch(os.path.join(self.settings, "drivers.json"), json.dumps({zelda: "mesa-26.3"}))
        lib = library.Library(DEFAULTS, self.settings, self.h.home, os.path.join(self.h.root, "runtime"),
                              logging.getLogger())
        lib.esde.bundled = lambda: ARM_FILES
        lib.watch_mounts()
        self.assertEqual(self.library_file(self.sd)["games"],
                         {"snes/Zelda.sfc": {"art": {"portrait": "sgdb:1"}, "driver": "mesa-26.3"}})
        # A game that is not on the card waits in the plugin's files.
        self.assertEqual(lib.picks.art, {gone: {"portrait": "sgdb:3"}, "app:12": {"hero": "sgdb:2"}})
        self.assertEqual(lib.picks.drivers, {})
        self.assertEqual(lib.choice(zelda, "portrait"), "sgdb:1")

    def test_a_library_mounted_elsewhere_keeps_its_tiles_and_picks(self):
        applied = {"name": "", "exe": "", "start_dir": "", "launch_options": ""}
        self.lib.combine_libraries(self.h.roms, [self.sd, self.games])
        self.lib.record(os.path.join(self.sd, "snes/Zelda.sfc"), 1, "snes", applied)
        self.lib.choose(os.path.join(self.sd, "snes/Zelda.sfc"), "portrait", "sgdb:1")
        self.lib.watch_mounts()
        self.mount("SN128")
        got = self.lib.mounts_changed()
        zelda = os.path.join(self.sd, "snes/Zelda.sfc")
        self.assertEqual(got["moved"], [{"where": "SN128/Emulation/roms", "drive": {"kind": "sd", "name": "MicroSD Card"}}])
        self.assertEqual(self.lib.roots(), [self.h.roms, self.sd, self.games])
        self.assertEqual(os.readlink(self.h.rom("snes")), os.path.join(self.sd, "snes"))
        self.assertEqual(self.lib.tiles[zelda]["appid"], 1)
        self.assertEqual(self.lib.choice(zelda, "portrait"), "sgdb:1")
        self.assertEqual([g["path"] for g in self.lib.games("snes")],
                         [os.path.join(self.sd, "snes", f) for f in ("Super Metroid.sfc", "Zelda.sfc")])
        self.assertIsNone(self.lib.mounts_changed())

    def test_a_tile_follows_its_game_moved_to_another_library(self):
        applied = {"name": "", "exe": "", "start_dir": "", "launch_options": ""}
        self.lib.combine_libraries(self.h.roms, [self.sd])
        moved, kept = self.h.rom("psp/LittleBigPlanet (Europe) (PSP) (PSN).iso"), os.path.join(self.sd, "gba/Metroid Fusion.gba")
        self.lib.record(moved, 1, "psp", applied)
        self.lib.record(kept, 2, "gba", applied)
        self.lib.choose(moved, "portrait", "sgdb:1")
        # David moves the PSP game from the internal storage to the card, then pulls the card out.
        os.remove(moved)
        os.remove(os.path.join(self.sd, "psp/LittleBigPlanet (Europe) (PSP) (PSN).iso"))
        touch(os.path.join(self.sd, "psp/LittleBigPlanet (Europe) (PSP) (PSN).iso"), "x" * 10)
        self.lib.sync_plan()
        card = os.path.join(self.sd, "psp/LittleBigPlanet (Europe) (PSP) (PSN).iso")
        self.assertEqual(self.lib.tiles[card]["appid"], 1)
        self.assertEqual(self.lib.choice(card, "portrait"), "sgdb:1")
        self.assertEqual(self.library_file(self.sd)["games"], {"psp/LittleBigPlanet (Europe) (PSP) (PSN).iso": {"art": {"portrait": "sgdb:1"}}})
        # A game without a tile takes its picks along too.
        self.lib.picks.keep(self.h.rom("psp/Patapon.iso"), {"art": {"hero": "sgdb:2"}, "driver": None})
        self.lib.sync_plan()
        self.assertEqual(self.lib.choice(os.path.join(self.sd, "psp/Patapon.iso"), "hero"), "sgdb:2")
        self.assertEqual(self.lib.picks.art, {})
        # A tile on a card that is out keeps its path, even with a copy of its game elsewhere.
        touch(self.h.rom("gba/Metroid Fusion.gba"), "x" * 80)
        os.rename(self.card, self.card + ".out")
        self.lib.sync_plan()
        self.assertIn(kept, self.lib.tiles)

    def test_a_card_with_another_library_is_reported(self):
        self.lib.use_library(self.h.roms)
        self.lib.watch_mounts()
        self.mount("SN128")
        got = self.lib.mounts_changed()
        self.assertEqual(got, {"moved": [], "found": [
            {"where": "SN128/Emulation/roms", "drive": {"kind": "sd", "name": "MicroSD Card"}, "games": 5}]})

    def test_without_roots_cards_are_still_read(self):
        self.assertEqual(self.lib.esde.rom_dirs(), [self.h.roms + "/", self.sd + "/"])


if __name__ == "__main__":
    unittest.main()
