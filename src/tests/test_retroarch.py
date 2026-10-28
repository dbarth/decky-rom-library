"""Tests for RetroArch's settings. Run with: python3 -I tests/test_retroarch.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from rom_library import retroarch  # noqa: E402

CONFIG = ".var/app/org.libretro.RetroArch/config/retroarch"
# retroarch.cfg on the Odin: the cores and their .info files in the Flatpak's folders, the bezel on.
GLOBAL = (f'libretro_directory = "~/{CONFIG}/cores"\nlibretro_info_path = "/app/share/libretro/info"\n'
          f'rgui_config_directory = "~/{CONFIG}/config"\ninput_overlay_enable = "true"\n'
          'rewind_enable = "false"\nrun_ahead_enabled = "false"\nrun_ahead_frames = "1"\n')
# A game override from the Odin's bezel pack.
PACMAN = (f'input_overlay = "~/{CONFIG}/overlays/ArcadeBezels/pacman.cfg"\ninput_overlay_enable = "true"\n'
          'input_overlay_opacity = "1.000000"\n')
ROM = "/home/steamos/Emulation/roms/fbneo/pacman.zip"


class RetroArchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.config = os.path.join(self.home, CONFIG)
        self.write("retroarch.cfg", GLOBAL)
        self.write("cores/fbneo_libretro.info", 'display_name = "Arcade (FinalBurn Neo)"\ncorename = "FinalBurn Neo"\n')
        self.write("overlays/ArcadeBezels/pacman.cfg", "overlays = 1\n")
        self.ra = retroarch.RetroArch(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.config, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def read(self, rel):
        with open(os.path.join(self.config, rel)) as f:
            return f.read()

    def test_a_game_without_override_takes_the_global_values(self):
        got = self.ra.settings("fbneo_libretro.so", ROM)
        self.assertEqual(got["id"], "pacman")
        self.assertEqual(got["globals"], {"bezel": "true", "rewind": "false", "run_ahead": "0"})
        self.assertEqual(set(got["values"].values()), {None})
        self.assertFalse(got["overlay"])

    def test_a_value_the_same_as_the_global_one_is_the_global_one(self):
        self.write("config/FinalBurn Neo/pacman.cfg", PACMAN)
        got = self.ra.settings("fbneo_libretro.so", ROM)
        self.assertIsNone(got["values"]["bezel"])
        self.assertTrue(got["overlay"])

    def test_the_core_and_the_folder_come_before_the_game(self):
        self.write("config/FinalBurn Neo/FinalBurn Neo.cfg", 'rewind_enable = "true"\n')
        self.write("config/FinalBurn Neo/fbneo.cfg", 'run_ahead_enabled = "true"\nrun_ahead_frames = "2"\n')
        got = self.ra.settings("fbneo_libretro.so", ROM)
        self.assertEqual((got["globals"]["rewind"], got["globals"]["run_ahead"]), ("true", "2"))

    def test_a_games_settings_go_in_its_override(self):
        self.write("config/FinalBurn Neo/pacman.cfg", PACMAN)
        self.ra.set("fbneo_libretro.so", ROM, "bezel", "false")
        self.ra.set("fbneo_libretro.so", ROM, "run_ahead", "1")
        self.assertEqual(self.read("config/FinalBurn Neo/pacman.cfg"),
                         PACMAN.replace('input_overlay_enable = "true"\n', "")
                         + 'input_overlay_enable = "false"\nrun_ahead_enabled = "true"\nrun_ahead_frames = "1"\n')
        values = self.ra.settings("fbneo_libretro.so", ROM)["values"]
        self.assertEqual((values["bezel"], values["run_ahead"], values["rewind"]), ("false", "1", None))
        self.ra.set("fbneo_libretro.so", ROM, "run_ahead", None)
        self.ra.set("fbneo_libretro.so", ROM, "bezel", "true")
        self.assertEqual(self.read("config/FinalBurn Neo/pacman.cfg"),
                         PACMAN.replace('input_overlay_enable = "true"\n', ""))

    def test_an_override_without_values_goes(self):
        self.ra.set("fbneo_libretro.so", ROM, "rewind", "true")
        self.assertEqual(self.read("config/FinalBurn Neo/pacman.cfg"), 'rewind_enable = "true"\n')
        self.ra.set("fbneo_libretro.so", ROM, "rewind", None)
        self.assertFalse(os.path.exists(os.path.join(self.config, "config/FinalBurn Neo/pacman.cfg")))

    def test_run_ahead_off_overrides_the_folders_frames(self):
        self.write("config/FinalBurn Neo/fbneo.cfg", 'run_ahead_enabled = "true"\nrun_ahead_frames = "2"\n')
        self.ra.set("fbneo_libretro.so", ROM, "run_ahead", "0")
        self.assertEqual(self.read("config/FinalBurn Neo/pacman.cfg"), 'run_ahead_enabled = "false"\n')
        self.assertEqual(self.ra.settings("fbneo_libretro.so", ROM)["values"]["run_ahead"], "0")

    def test_the_core_name_comes_from_the_flatpaks_info_files(self):
        info = os.path.join(self.home, ".local/share/flatpak/app/org.libretro.RetroArch/current/active/files"
                            "/share/libretro/info/parallel_n64_libretro.info")
        os.makedirs(os.path.dirname(info))
        with open(info, "w") as f:
            f.write('corename = "ParaLLEl N64"\n')
        self.ra.set("parallel_n64_libretro.so", "/roms/n64/Mario Kart 64 (Europe).zip", "rewind", "true")
        self.assertEqual(self.read("config/ParaLLEl N64/Mario Kart 64 (Europe).cfg"), 'rewind_enable = "true"\n')

    def test_a_core_without_info_has_no_settings(self):
        self.assertIsNone(self.ra.settings("vice_x64sc_libretro.so", "/roms/c64/Arkanoid.d64"))
        with self.assertRaises(ValueError):
            self.ra.set("vice_x64sc_libretro.so", "/roms/c64/Arkanoid.d64", "rewind", "true")

    def test_unknown_values_raise(self):
        for name, value in (("bezel", "on"), ("run_ahead", "two"), ("shader", "crt")):
            with self.assertRaises(ValueError):
                self.ra.set("fbneo_libretro.so", ROM, name, value)


if __name__ == "__main__":
    unittest.main()
