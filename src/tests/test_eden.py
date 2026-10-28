"""Tests for Eden's settings. Run with: python3 -I tests/test_eden.py"""
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from rom_library import eden  # noqa: E402

SYSTEM_LANGUAGE = eden.system_language

# The head of the [UI] section as Eden writes it, with its default question before a game stops,
# then player 1 on a gamepad.
UI = ("[UI]\ntheme\\default=true\ntheme=default\nconfirmStop\\default=true\nconfirmStop=0\n"
      "showStatusBar\\default=true\nshowStatusBar=true\nfullscreen\\default=true\nfullscreen=false\n"
      "check_for_updates\\default=true\ncheck_for_updates=true\n"
      "pauseWhenInBackground\\default=true\npauseWhenInBackground=false\n\n[Core]\nuse_multi_core=true\n"
      '[Controls]\nplayer_0_button_a\\default=false\nplayer_0_button_a="engine:sdl,port:0,button:0"\n')
# The same once set up.
SET_UP = (UI.replace("confirmStop\\default=true\nconfirmStop=0", "confirmStop\\default=false\nconfirmStop=2")
          .replace("showStatusBar\\default=true\nshowStatusBar=true", "showStatusBar\\default=false\nshowStatusBar=false")
          .replace("fullscreen\\default=true\nfullscreen=false", "fullscreen\\default=false\nfullscreen=true")
          .replace("check_for_updates\\default=true\ncheck_for_updates=true",
                   "check_for_updates\\default=false\ncheck_for_updates=false"))

# Eden's window_state.ini on the Odin: a 1280x720 window at (320, 159) on a 1920 px screen, not maximized.
GEOMETRY = ("@ByteArray(\\x1\\xd9\\xd0\\xcb\\0\\x3\\0\\0\\0\\0\\x1@\\0\\0\\0\\x9f\\0\\0\\x6?\\0\\0\\x3n"
            "\\0\\0\\x1@\\0\\0\\0\\x9f\\0\\0\\x6?\\0\\0\\x3n\\0\\0\\0\\0\\0\\0\\0\\0\\a\\x80"
            "\\0\\0\\x1@\\0\\0\\0\\x9f\\0\\0\\x6?\\0\\0\\x3n)")
STATE = ("[General]\ngameListHeaderState=@ByteArray(\\0\\0\\0\\xff\\0\\0\\0\\0\\0\\0\\0\\x1)\n"
         f"geometry={GEOMETRY}\ngeometryRenderWindow=@ByteArray()\n")

# Player 1's motion on the keyboard, as the Odin had it, then on the DSU server.
KEYBOARD = ("[Controls]\nmotion_enabled\\default=true\nmotion_enabled=true\n"
            "player_0_motionleft\\default=false\nplayer_0_motionleft=\"engine:keyboard,code:55,toggle:0\"\n"
            "player_0_motionright\\default=false\nplayer_0_motionright=\"engine:keyboard,code:56,toggle:0\"\n")
DSU = (KEYBOARD.replace('"engine:keyboard,code:55,toggle:0"', eden.DSU_MOTION)
       .replace('"engine:keyboard,code:56,toggle:0"', eden.DSU_MOTION))
# Player 1's buttons after the motion, as Eden writes them, then the game's copy with A and B swapped.
PLAYER = ("player_0_profile_name\\default=true\nplayer_0_profile_name=\n"
          'player_0_button_a\\default=false\nplayer_0_button_a="engine:sdl,port:0,button:0"\n'
          'player_0_button_b\\default=false\nplayer_0_button_b="engine:sdl,port:0,button:1"\n'
          'player_0_button_x\\default=false\nplayer_0_button_x="engine:sdl,port:0,button:2"\n')
SWAPPED = (f"player_0_motionleft\\default=false\nplayer_0_motionleft={eden.DSU_MOTION}\n"
           f"player_0_motionright\\default=false\nplayer_0_motionright={eden.DSU_MOTION}\n"
           "player_0_profile_name\\default=false\nplayer_0_profile_name=Swap A and B\n"
           'player_0_button_a\\default=false\nplayer_0_button_a="engine:sdl,port:0,button:1"\n'
           'player_0_button_b\\default=false\nplayer_0_button_b="engine:sdl,port:0,button:0"\n'
           'player_0_button_x\\default=false\nplayer_0_button_x="engine:sdl,port:0,button:2"\n')


class EdenTest(unittest.TestCase):
    def setUp(self):
        eden.screen = lambda: (1920, 1080)
        eden.dsu.running = lambda: False
        eden.system_language = lambda: None
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        os.makedirs(os.path.join(self.home, ".config", "eden"))
        self.e = eden.Eden(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, path=None):
        with open(path or self.e.ini, "w") as f:
            f.write(text)

    def read(self, path=None):
        with open(path or self.e.ini) as f:
            return f.read()

    def test_setup_stops_without_a_question(self):
        self.write(UI)
        self.assertEqual(self.e.setup(), [self.e.ini])
        self.assertEqual(self.read(), SET_UP)
        self.assertEqual(self.e.setup(), [])

    def test_setup_keeps_the_users_choice(self):
        text = (UI.replace("confirmStop\\default=true\nconfirmStop=0", "confirmStop\\default=false\nconfirmStop=1")
                .replace("showStatusBar\\default=true", "showStatusBar\\default=false")
                .replace("fullscreen\\default=true", "fullscreen\\default=false")
                .replace("check_for_updates\\default=true", "check_for_updates\\default=false"))
        self.write(text)
        self.assertFalse(self.e.setup())
        self.assertEqual(self.read(), text)

    def test_setup_adds_the_keys_to_a_config_without_them(self):
        self.write("[UI]\ntheme=default\n[Core]\nuse_multi_core=true\n")
        self.e.setup()
        lines = self.read().splitlines()
        for key, value in (("confirmStop", "2"), ("showStatusBar", "false"), ("fullscreen", "true"),
                           ("check_for_updates", "false")):
            self.assertEqual(eden.qt_value(lines, "UI", key, None), value)
        self.assertEqual(eden.qt_value(lines, "Controls", "player_0_button_a", None), f'"{eden.PAD},button:0"')

    def test_setup_maps_player_1_to_the_gamepad(self):
        self.write('[Controls]\nplayer_0_button_a\\default=true\nplayer_0_button_a="engine:keyboard,code:67,toggle:0"\n')
        self.e.setup()
        lines = self.read().splitlines()
        self.assertEqual(eden.qt_value(lines, "Controls", "player_0_button_a", None), f'"{eden.PAD},button:0"')
        self.assertEqual(eden.qt_value(lines, "Controls", "player_0_button_zl", None),
                         f'"{eden.PAD},axis:2,threshold:0.500000,invert:+"')
        self.assertEqual(eden.qt_value(lines, "Controls", "player_0_button_dup", None),
                         f'"{eden.PAD},hat:0,direction:up"')
        self.assertIn("axis_x:3,axis_y:4,", eden.qt_value(lines, "Controls", "player_0_rstick", None))
        # Player 1 on another controller stays there.
        text = '[Controls]\nplayer_0_button_a\\default=false\nplayer_0_button_a="engine:sdl,port:0,button:5"\n'
        self.write(text)
        self.e.setup()
        self.assertEqual(eden.qt_value(self.read().splitlines(), "Controls", "player_0_button_a", None),
                         '"engine:sdl,port:0,button:5"')

    def test_setup_takes_the_systems_language(self):
        for lang, index in (("fr_FR.UTF-8", "2"), ("en_GB.UTF-8", "12"), ("pt_BR.UTF-8", "17"), ("de_CH", "3"),
                            ("es_MX.UTF-8", "14"), ("xx_YY.UTF-8", None)):
            with mock.patch.dict(os.environ, {"LANG": lang}, clear=True):
                self.assertEqual(SYSTEM_LANGUAGE(), index, lang)
        eden.system_language = lambda: "2"
        self.write(UI)
        self.e.setup()
        self.assertEqual(eden.qt_value(self.read().splitlines(), "System", "language_index", None), "2")
        self.write(UI + "[System]\nlanguage_index\\default=false\nlanguage_index=3\n")
        self.e.setup()
        self.assertEqual(eden.qt_value(self.read().splitlines(), "System", "language_index", None), "3")

    def test_setup_adds_the_folder_of_updates_once(self):
        self.write(UI.replace("[UI]\n", "[UI]\nPaths\\external_content_dirs\\size=0\n"))
        self.e.setup("/roms/switch/updates")
        self.e.setup("/roms/switch/updates")
        lines = self.read().splitlines()
        self.assertEqual(eden.qt_get(lines, "UI", "Paths\\external_content_dirs\\size"), "1")
        self.assertEqual(eden.qt_get(lines, "UI", "Paths\\external_content_dirs\\1\\path"), "/roms/switch/updates")

    def test_setup_gives_the_window_the_screens_size(self):
        self.write(STATE, self.e.state)
        self.assertEqual(self.e.setup(), [self.e.state])
        data = eden.qt_bytes(eden.qt_get(self.read(self.e.state).splitlines(), "General", "geometry"))
        rects = struct.unpack(eden.GEOMETRY, data)
        self.assertEqual(rects[3:7], (0, 0, 1919, 1079))
        self.assertEqual(rects[7:11], (0, 0, 1919, 1079))
        self.assertEqual(rects[12:15], (1, 0, 1920))
        self.assertEqual(rects[15:], (0, 0, 1919, 1079))
        self.assertIn("gameListHeaderState=", self.read(self.e.state))
        self.assertEqual(self.e.setup(), [])

    def test_setup_without_a_screen_keeps_the_window(self):
        eden.screen = lambda: None
        self.write(STATE, self.e.state)
        self.assertEqual(self.e.setup(), [])
        self.assertEqual(self.read(self.e.state), STATE)

    def test_bytearray_reads_and_writes_as_qt(self):
        data = eden.qt_bytes(GEOMETRY)
        self.assertEqual(len(data), 66)
        self.assertEqual(data[8:12], (320).to_bytes(4, "big"))
        self.assertEqual(eden.qt_bytearray(data), GEOMETRY)
        # A digit after \0 is escaped, and = puts the value in quotes.
        self.assertEqual(eden.qt_bytearray(b"\x001="), '"@ByteArray(\\0\\x31=)"')
        self.assertEqual(eden.qt_bytes('"@ByteArray(\\0\\x31=)"'), b"\x001=")
        self.assertIsNone(eden.qt_bytes("1280"))

    def test_setup_without_eden_does_nothing(self):
        self.assertFalse(self.e.setup())
        self.assertFalse(os.path.exists(self.e.ini))

    def test_flatpak_config(self):
        os.rmdir(os.path.join(self.home, ".config", "eden"))
        folder = os.path.join(self.home, ".var", "app", "dev.eden_emu.eden", "config", "eden")
        os.makedirs(folder)
        self.assertEqual(eden.Eden(self.home).ini, os.path.join(folder, "qt-config.ini"))

    def test_setup_moves_motion_to_the_dsu_server(self):
        eden.dsu.running = lambda: True
        self.write(KEYBOARD)
        self.e.setup()
        lines = self.read().splitlines()
        for key in eden.MOTIONS:
            self.assertEqual(eden.qt_value(lines, "Controls", key, None), eden.DSU_MOTION)
        self.assertEqual(self.e.settings("01007EF00011E000")["globals"]["gyro"], "true")

    def test_setup_keeps_motion_from_a_controller(self):
        eden.dsu.running = lambda: True
        text = KEYBOARD.replace("engine:keyboard,code:55,toggle:0", "engine:sdl,motion:0,port:0")
        self.write(text)
        self.e.setup()
        self.assertIn("engine:sdl,motion:0,port:0", self.read())
        self.assertEqual(self.e.settings("01007EF00011E000")["globals"]["gyro"], "false")

    def test_setup_without_a_dsu_server_keeps_the_keyboard(self):
        self.write(KEYBOARD)
        self.e.setup()
        self.assertIn('player_0_motionleft="engine:keyboard,code:55,toggle:0"\n', self.read())

    def test_a_games_gyroscope_goes_in_its_own_file(self):
        self.write(DSU)
        custom = self.e.custom("01007EF00011E000")
        self.assertIsNone(self.e.settings("01007EF00011E000")["values"]["gyro"])
        self.e.set("01007EF00011E000", "gyro", "false")
        self.assertEqual(self.read(custom), "[Controls]\nmotion_enabled\\use_global=false\n"
                                            "motion_enabled\\default=false\nmotion_enabled=false\n")
        self.assertEqual(self.e.settings("01007EF00011E000")["values"]["gyro"], "false")
        self.e.set("01007EF00011E000", "gyro", "true")
        self.assertEqual(self.e.settings("01007EF00011E000")["values"]["gyro"], "true")
        self.e.set("01007EF00011E000", "gyro", None)
        self.assertEqual(self.read(custom), "[Controls]\nmotion_enabled\\use_global=true\n")
        with self.assertRaises(ValueError):
            self.e.set("01007EF00011E000", "gyro", "on")

    def test_a_games_settings_read_the_global_ones_first(self):
        self.write("[Renderer]\ngpu_accuracy\\default=false\ngpu_accuracy=0\n"
                   "scaling_filter\\default=true\nscaling_filter=6\n[System]\nlanguage_index\\default=false\n"
                   "language_index=2\n")
        got = self.e.settings("0100DA801624E000")
        self.assertEqual(got["globals"]["accuracy"], "0")
        self.assertEqual(got["globals"]["filter"], "0")
        self.assertEqual(got["globals"]["language"], "2")
        self.assertEqual(got["globals"]["reactive_flushing"], "true")
        self.assertEqual(set(got["values"].values()), {None})

    def test_a_games_settings_go_in_their_sections(self):
        self.write(UI)
        custom = self.e.custom("0100DA801624E000")
        self.e.set("0100DA801624E000", "accuracy", "0")
        self.e.set("0100DA801624E000", "docked", "1")
        self.e.set("0100DA801624E000", "async_shaders", "true")
        self.assertEqual(self.read(custom), "[Renderer]\nuse_asynchronous_shaders\\use_global=false\n"
                                            "use_asynchronous_shaders\\default=false\nuse_asynchronous_shaders=true\n"
                                            "gpu_accuracy\\use_global=false\ngpu_accuracy\\default=false\n"
                                            "gpu_accuracy=0\n[System]\nuse_docked_mode\\use_global=false\n"
                                            "use_docked_mode\\default=true\nuse_docked_mode=1\n")
        values = self.e.settings("0100DA801624E000")["values"]
        self.assertEqual((values["accuracy"], values["docked"], values["async_shaders"]), ("0", "1", "true"))
        for name, value in (("accuracy", "low"), ("async_shaders", "1"), ("vsync", "1"), ("swap", "1")):
            with self.assertRaises(ValueError):
                self.e.set("0100DA801624E000", name, value)

    def test_a_game_swaps_a_and_b_in_a_copy_of_player_1(self):
        self.write(DSU + PLAYER)
        custom = self.e.custom("01007EF00011E000")
        self.e.set("01007EF00011E000", "gyro", "false")
        self.e.set("01007EF00011E000", "swap", "true")
        self.assertEqual(self.read(custom), "[Controls]\n" + SWAPPED + "motion_enabled\\use_global=false\n"
                                            "motion_enabled\\default=false\nmotion_enabled=false\n")
        self.assertEqual(self.e.settings("01007EF00011E000")["values"]["swap"], "true")
        # The copy follows the global buttons at the next start.
        self.write((DSU + PLAYER).replace("button:2", "button:4"))
        self.e.prepare("01007EF00011E000")
        self.assertIn('player_0_button_x="engine:sdl,port:0,button:4"\n', self.read(custom))
        self.e.set("01007EF00011E000", "swap", None)
        self.assertEqual(self.read(custom), "[Controls]\nmotion_enabled\\use_global=false\n"
                                            "motion_enabled\\default=false\nmotion_enabled=false\n")
        self.assertIsNone(self.e.settings("01007EF00011E000")["values"]["swap"])

    def test_a_game_cannot_swap_buttons_eden_has_not_mapped(self):
        self.write(UI)
        with self.assertRaises(ValueError):
            self.e.set("01007EF00011E000", "swap", "true")


if __name__ == "__main__":
    unittest.main()
