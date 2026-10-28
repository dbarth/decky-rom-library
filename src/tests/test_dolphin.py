"""Tests for Dolphin's settings per game. Run with: python3 -I tests/test_dolphin.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from rom_library import dolphin  # noqa: E402


# The gyroscope of the first Wii Remote on the DSU server named Odin.
ODIN_GYRO = "".join(f"{k} = `DSUClient/0/Odin:Gyro {k.split('/')[1]}`\n" for k in dolphin.GYRO)


class DolphinTest(unittest.TestCase):
    def setUp(self):
        dolphin.dsu.running = lambda: False
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.config = os.path.join(self.home, ".config", "dolphin-emu")
        os.makedirs(self.config)
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = SDL/0/SteamOS Handheld Controller\nExtension = Nunchuk\n")
        self.write("GFX.ini", "[Settings]\nInternalResolution = 2\n")
        pads = os.path.join(self.home, dolphin.STEAM_PADS)
        os.makedirs(os.path.dirname(pads))
        with open(pads, "w") as f:
            f.write("[slot 0]\nname=SteamOS Handheld Controller\nVID=0x28de\nPID=0x12f0\n")
        self.d = dolphin.Dolphin(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        with open(os.path.join(self.config, name), "w") as f:
            f.write(text)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_a_game_keeps_the_global_values(self):
        s = self.d.settings("SMNP01")
        self.assertEqual(s["values"], {"aspect": None, "resolution": None, "backend": None, "wiimote": None,
                                       "gyro": None})
        self.assertEqual(s["globals"], {"aspect": "0", "resolution": "2", "backend": "OGL",
                                        "wiimote": dolphin.NUNCHUK, "gyro": "false"})

    def test_a_value_goes_in_the_game_ini_and_global_removes_it(self):
        self.d.set("SMNP01", "aspect", "1")
        self.d.set("SMNP01", "resolution", "3")
        ini = os.path.join(self.home, ".local", "share", "dolphin-emu", "GameSettings", "SMNP01.ini")
        self.assertEqual(self.read(ini), "[Video_Settings]\nAspectRatio = 1\nInternalResolution = 3\n")
        self.d.set("SMNP01", "aspect", None)
        self.assertEqual(self.d.settings("SMNP01")["values"]["resolution"], "3")
        self.d.set("SMNP01", "resolution", None)
        self.assertEqual(self.read(ini), "")

    def test_a_layout_saves_its_profile_on_the_global_device(self):
        self.d.set("SMNP01", "wiimote", dolphin.SIDEWAYS)
        profile = self.read(self.d.profile(dolphin.SIDEWAYS))
        self.assertTrue(profile.startswith("[Profile]\nDevice = SDL/0/SteamOS Handheld Controller\n"))
        self.assertIn("Options/Sideways Wiimote = True\n", profile)
        self.assertEqual(self.d.settings("SMNP01")["values"]["wiimote"], dolphin.SIDEWAYS)

    def test_a_layout_keeps_a_profile_edited_in_dolphin(self):
        path = self.d.profile(dolphin.CLASSIC)
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write("[Profile]\nExtension = Classic\n")
        self.d.set("RMGP01", "wiimote", dolphin.CLASSIC)
        self.assertEqual(self.read(path), "[Profile]\nExtension = Classic\n")

    def test_an_unknown_layout_fails(self):
        with self.assertRaises(ValueError):
            self.d.set("SMNP01", "wiimote", "Balance Board")

    def test_setup_moves_the_keyboard_defaults_to_steams_gamepad(self):
        self.write("Dolphin.ini", "[General]\nISOPaths = 0\n")
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = XInput2/0/Virtual core pointer\nButtons/2 = `2`\n"
                   "[Wiimote2]\nDevice = XInput2/0/Virtual core pointer\n")
        self.d.setup()
        self.assertEqual(self.read(os.path.join(self.config, "Dolphin.ini")),
                         "[General]\nISOPaths = 0\n[Display]\nFullscreen = True\n")
        wiimote = self.read(os.path.join(self.config, "WiimoteNew.ini"))
        self.assertTrue(wiimote.startswith("[Wiimote2]\nDevice = XInput2/0/Virtual core pointer\n[Wiimote1]\n"
                                           "Device = SDL/0/SteamOS Handheld Controller\n"))
        self.assertIn("Buttons/2 = `Button N`\n", wiimote)
        self.assertNotIn("`2`", wiimote)
        self.assertIn("Buttons/A = `Button S`\n", self.read(os.path.join(self.config, "GCPadNew.ini")))

    def test_setup_keeps_what_the_user_set(self):
        self.write("Dolphin.ini", "[Display]\nFullscreen = False\n")
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = SDL/0/Xbox Series X Controller\n")
        self.d.setup()
        self.assertEqual(self.read(os.path.join(self.config, "Dolphin.ini")), "[Display]\nFullscreen = False\n")
        self.assertEqual(self.read(os.path.join(self.config, "WiimoteNew.ini")),
                         "[Wiimote1]\nDevice = SDL/0/Xbox Series X Controller\n")

    def test_setup_without_a_steam_gamepad_keeps_the_keyboard(self):
        os.remove(os.path.join(self.home, dolphin.STEAM_PADS))
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = XInput2/0/Virtual core pointer\n")
        self.d.setup()
        self.assertEqual(self.read(os.path.join(self.config, "WiimoteNew.ini")),
                         "[Wiimote1]\nDevice = XInput2/0/Virtual core pointer\n")

    def test_a_sideways_game_gets_its_layout_once(self):
        self.d.prepare("SMNP01")
        self.assertEqual(self.d.settings("SMNP01")["values"]["wiimote"], dolphin.SIDEWAYS)
        self.d.set("SMNP01", "wiimote", None)
        self.d.prepare("SMNP01")
        self.assertIsNone(self.d.settings("SMNP01")["values"]["wiimote"])

    def test_other_games_keep_the_global_layout(self):
        self.d.prepare("RMGP01")
        self.assertFalse(os.path.exists(self.d.game_ini("RMGP01")))

    def test_a_layout_takes_steams_gamepad_from_a_keyboard_global(self):
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = XInput2/0/Virtual core pointer\n")
        self.d.set("SMNP01", "wiimote", dolphin.SIDEWAYS)
        self.assertIn("Device = SDL/0/SteamOS Handheld Controller\n", self.read(self.d.profile(dolphin.SIDEWAYS)))

    def test_the_global_layout_follows_wiimote_new(self):
        self.write("WiimoteNew.ini", "[Wiimote1]\nOptions/Sideways Wiimote = True\n")
        self.assertEqual(self.d.global_layout(), dolphin.SIDEWAYS)
        self.write("WiimoteNew.ini", "[Wiimote1]\nExtension = Classic\n")
        self.assertEqual(self.d.global_layout(), dolphin.CLASSIC)

    def test_setup_adds_the_dsu_server_once_with_the_gyroscope(self):
        dolphin.dsu.running = lambda: True
        self.d.setup()
        self.assertEqual(self.read(os.path.join(self.config, "DSUClient.ini")),
                         "[Server]\nEntries = Handheld:127.0.0.1:26760;\nEnabled = True\n")
        wiimote = os.path.join(self.config, "WiimoteNew.ini")
        self.assertIn("IMUGyroscope/Yaw Left = `DSUClient/0/Handheld:Gyro Yaw Left`\n", self.read(wiimote))
        self.assertEqual(self.d.settings("SMNP01")["globals"]["gyro"], "true")
        # The user takes the gyroscope off the Wii Remote in Dolphin.
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = SDL/0/SteamOS Handheld Controller\nExtension = Nunchuk\n")
        self.d.setup()
        self.assertNotIn("IMUGyroscope", self.read(wiimote))

    def test_setup_keeps_the_users_dsu_server(self):
        dolphin.dsu.running = lambda: True
        self.write("DSUClient.ini", "[Server]\nEnabled = True\nEntries = Odin:127.0.0.1:26760;\n")
        self.d.setup()
        self.assertEqual(self.read(os.path.join(self.config, "DSUClient.ini")),
                         "[Server]\nEnabled = True\nEntries = Odin:127.0.0.1:26760;\n")
        self.assertNotIn("IMUGyroscope", self.read(os.path.join(self.config, "WiimoteNew.ini")))
        self.assertEqual(self.d.dsu_pad(), "DSUClient/0/Odin")

    def test_setup_without_a_dsu_server_adds_none(self):
        self.d.setup()
        self.assertFalse(os.path.exists(os.path.join(self.config, "DSUClient.ini")))

    def test_a_keyboard_wii_remote_moves_to_steams_gamepad_with_the_gyroscope(self):
        self.write("DSUClient.ini", "[Server]\nEnabled = True\nEntries = Odin:127.0.0.1:26760;\n")
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = XInput2/0/Virtual core pointer\n")
        self.d.setup()
        self.assertIn(ODIN_GYRO, self.read(os.path.join(self.config, "WiimoteNew.ini")))

    def test_a_games_gyroscope_names_its_profile(self):
        self.write("DSUClient.ini", "[Server]\nEnabled = True\nEntries = Odin:127.0.0.1:26760;\n")
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = SDL/0/SteamOS Handheld Controller\nExtension = Nunchuk\n"
                   + ODIN_GYRO)
        self.d.set("RMGP01", "gyro", "false")
        self.assertEqual(self.d.settings("RMGP01")["values"]["gyro"], "false")
        self.assertIsNone(self.d.settings("RMGP01")["values"]["wiimote"])
        self.assertEqual(self.read(self.d.profile("Global without gyroscope")),
                         "[Profile]\nDevice = SDL/0/SteamOS Handheld Controller\nExtension = Nunchuk\n")
        self.d.set("RMGP01", "wiimote", dolphin.CLASSIC)
        self.assertEqual(self.d.settings("RMGP01")["values"]["wiimote"], dolphin.CLASSIC)
        self.assertNotIn("IMUGyroscope", self.read(self.d.profile("Classic Controller without gyroscope")))
        self.d.set("RMGP01", "gyro", None)
        self.assertIn(ODIN_GYRO, self.read(self.d.profile(dolphin.CLASSIC)))
        self.d.set("RMGP01", "wiimote", None)
        self.assertEqual(self.read(self.d.game_ini("RMGP01")), "")

    def test_a_layouts_profile_follows_the_global_gyroscope(self):
        self.d.set("SMNP01", "wiimote", dolphin.SIDEWAYS)
        self.d.set("RMGP01", "gyro", "true")
        self.assertNotIn("IMUGyroscope", self.read(self.d.profile(dolphin.SIDEWAYS)))
        self.write("DSUClient.ini", "[Server]\nEnabled = True\nEntries = Odin:127.0.0.1:26760;\n")
        self.write("WiimoteNew.ini", "[Wiimote1]\nDevice = SDL/0/SteamOS Handheld Controller\n" + ODIN_GYRO)
        self.d.setup()
        self.assertIn(ODIN_GYRO, self.read(self.d.profile(dolphin.SIDEWAYS)))
        self.assertIn(ODIN_GYRO, self.read(self.d.profile("Global with gyroscope")))

    def test_an_unknown_gyroscope_fails(self):
        with self.assertRaises(ValueError):
            self.d.set("SMNP01", "gyro", "on")


if __name__ == "__main__":
    unittest.main()
