"""Tests for the classification of shortcuts that are not tiles. Run with: python3 -I tests/test_apps.py"""
import json
import logging
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, HERE)

from rom_library import apps, library  # noqa: E402
from test_esde import ARM_FILES, Home, touch  # noqa: E402

DEFAULTS = os.path.join(HERE, "..", "backend", "defaults")
LOADOUT_RULE = """<?xml version="1.0"?>
<ruleList>
    <emulator name="DOLPHIN">
        <rule type="staticpath">
            <entry>~/.local/share/steamos-arm/hub/bin/dolphin</entry>
        </rule>
    </emulator>
</ruleList>
"""


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        rules = os.path.join(self.h.home, "ES-DE", "custom_systems", "es_find_rules.xml")
        touch(rules, LOADOUT_RULE)
        self.dolphin = os.path.join(self.h.home, ".local/share/steamos-arm/hub/bin/dolphin")
        touch(self.dolphin, mode=0o755)
        self.esde = os.path.join(self.h.home, "Applications", "ES-DE.AppImage")
        touch(self.esde, mode=0o755)
        self.binaries, self.flatpaks = self.h.es.emulator_binaries()

    def tearDown(self):
        self.h.cleanup()

    def kind(self, exe, options=""):
        return apps.classify({"exe": f'"{exe}"', "launch_options": options}, self.binaries, self.flatpaks,
                             self.h.es.binary())

    def test_emulators(self):
        self.assertEqual(self.kind(self.dolphin), apps.EMULATOR)
        self.assertEqual(self.kind(os.path.join(self.h.home, "Applications", "Eden.AppImage"), "-f"), apps.EMULATOR)
        self.assertEqual(self.kind("/usr/bin/flatpak", '"run" "org.libretro.RetroArch"'), apps.EMULATOR)
        self.assertEqual(self.kind("/usr/bin/flatpak", "run --branch=stable org.libretro.RetroArch"), apps.EMULATOR)
        self.assertEqual(self.kind("/var/lib/flatpak/exports/bin/org.libretro.RetroArch"), apps.EMULATOR)

    def test_a_shortcut_that_opens_a_game_is_not_an_emulator(self):
        self.assertEqual(self.kind(self.dolphin, "%command% -b -e /home/u/roms/wii/game.rvz"), apps.OTHER)
        self.assertEqual(self.kind("/usr/bin/flatpak", "run org.libretro.RetroArch -L core.so /roms/a.zip"),
                         apps.OTHER)

    def test_frontends(self):
        self.assertEqual(self.kind(self.esde), apps.FRONTEND)
        self.assertEqual(self.kind("/home/u/.local/share/steamos-arm/hub/bin/esde"), apps.FRONTEND)
        self.assertEqual(self.kind("/usr/bin/flatpak", "run org.pegasus_frontend.Pegasus"), apps.FRONTEND)
        self.assertEqual(self.kind("/usr/bin/flatpak", "run net.retrodeck.retrodeck"), apps.FRONTEND)

    def test_stores_and_others(self):
        self.assertEqual(self.kind("/usr/bin/konkr-apk", '"run" "com.android.vending"'), apps.OTHER)
        self.assertEqual(self.kind("/usr/bin/flatpak", "run com.heroicgameslauncher.hgl"), apps.OTHER)
        self.assertEqual(self.kind("/home/u/Games/game.exe"), apps.OTHER)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.settings = os.path.join(self.h.root, "settings")
        os.makedirs(self.settings)
        self.lib = library.Library(DEFAULTS, self.settings, self.h.home, os.path.join(self.h.root, "runtime"),
                                   logging.getLogger())
        self.lib.esde.bundled = lambda: ARM_FILES
        self.lib.record("/roms/fbneo/marble.zip", 7, "fbneo", {k: "" for k in library.FIELDS})
        self.shortcuts = [
            {"appid": 1, "name": "RetroArch", "exe": "/usr/bin/flatpak",
             "launch_options": "run org.libretro.RetroArch", "art": False},
            {"appid": 2, "name": "Google Play Store", "exe": "/usr/bin/konkr-apk",
             "launch_options": "run com.android.vending", "art": True},
            {"appid": 7, "name": "Marble Madness", "exe": "/usr/bin/flatpak",
             "launch_options": "run org.libretro.RetroArch -L c /roms/fbneo/marble.zip", "art": True},
        ]

    def tearDown(self):
        self.h.cleanup()

    def test_tiles_stay_out(self):
        plan = self.lib.apps_plan(self.shortcuts)
        self.assertEqual([(a["appid"], a["kind"], a["art"]) for a in plan["apps"]],
                         [(1, "emulator", True), (2, "other", False)])

    def test_the_launcher_stays_out(self):
        self.lib.set_launcher(2)
        self.assertEqual(self.lib.launcher(), 2)
        self.assertEqual([a["appid"] for a in self.lib.apps_plan(self.shortcuts)["apps"]], [1])

    def test_artwork_once_and_by_suffixed_name(self):
        self.lib.apps_plan(self.shortcuts)
        self.lib.app_art_done(1)
        self.assertFalse(self.lib.apps_plan(self.shortcuts)["apps"][0]["art"])
        media = self.lib.media(library.APPS, "app:1")
        self.assertEqual(media["sgdb_names"], ["RetroArch (Emulator)", "RetroArch (Program)", "RetroArch"])
        # Other apps, such as a store, stay out of the list.
        self.assertEqual([a["name"] for a in self.lib.app_list()], ["RetroArch"])
        with open(os.path.join(self.settings, "apps.json")) as f:
            self.assertEqual(json.load(f)["2"]["kind"], "other")


# Answers as hub.py does: remove starts a job, jobs lists it in HUB_STATE, steam-gone succeeds.
# Each call appends its arguments to the file named by HUB_LOG.
FAKE_HUB = """import json, os, sys
with open(os.environ["HUB_LOG"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
cmd = sys.argv[1]
if cmd == "remove":
    print(json.dumps({"id": "j1", "app": sys.argv[2], "state": "running"}))
elif cmd == "jobs":
    print(json.dumps({"jobs": [{"id": "j1", "state": os.environ["HUB_STATE"], "error": "flatpak failed"}]}))
else:
    print(json.dumps({"ok": True}))
"""


class HubTest(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        self.settings = os.path.join(self.h.root, "settings")
        os.makedirs(self.settings)
        self.lib = library.Library(DEFAULTS, self.settings, self.h.home, os.path.join(self.h.root, "runtime"),
                                   logging.getLogger())
        self.lib.esde.bundled = lambda: ARM_FILES
        hub = os.path.join(self.h.root, "hub.py")
        touch(hub, FAKE_HUB)
        self.lib.hub = [sys.executable, hub]
        self.log = os.path.join(self.h.root, "hub.log")
        os.environ["HUB_LOG"] = self.log
        touch(os.path.join(self.h.home, "ES-DE", "custom_systems", "es_find_rules.xml"), LOADOUT_RULE)
        dolphin = os.path.join(self.h.home, ".local/share/steamos-arm/hub/bin/dolphin")
        touch(dolphin, mode=0o755)
        self.lib.apps_plan([
            {"appid": 1, "name": "Dolphin", "exe": f'"{dolphin}"', "launch_options": "", "art": True},
            {"appid": 2, "name": "RetroArch", "exe": "/usr/bin/flatpak",
             "launch_options": "run org.libretro.RetroArch", "art": True},
        ])

    def tearDown(self):
        self.h.cleanup()

    def calls(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def test_only_the_hub_launchers_name_a_hub_app(self):
        self.assertEqual({a["name"]: a["hub"] for a in self.lib.app_list()}, {"Dolphin": "dolphin", "RetroArch": None})
        self.assertIsNone(self.lib.hub_app(os.path.join(self.lib.hub_bin, "gone")))

    def test_uninstall_waits_for_the_job_and_forgets_the_app(self):
        os.environ["HUB_STATE"] = "done"
        self.lib.uninstall_app(1)
        self.assertEqual(self.calls(), ["remove dolphin", "jobs", "steam-gone dolphin"])
        self.assertEqual([a["name"] for a in self.lib.app_list()], ["RetroArch"])

    def test_a_failed_job_keeps_the_app(self):
        os.environ["HUB_STATE"] = "failed"
        with self.assertRaisesRegex(RuntimeError, "flatpak failed"):
            self.lib.uninstall_app(1)
        self.assertEqual(self.calls(), ["remove dolphin", "jobs"])
        self.assertEqual(len(self.lib.app_list()), 2)

    def test_describe_tells_tiles_apps_and_the_launcher_apart(self):
        self.lib.record("/roms/fbneo/marble.zip", 7, "fbneo", {k: "" for k in library.FIELDS})
        self.lib.set_launcher(9)
        self.assertEqual(self.lib.describe(7), {"tile": "/roms/fbneo/marble.zip", "system": "fbneo"})
        self.assertEqual(self.lib.describe(1), {"kind": "emulator", "hub": "dolphin"})
        self.assertEqual(self.lib.describe(9), {"kind": "launcher"})
        self.assertIsNone(self.lib.describe(5))

    def test_an_app_outside_the_hub_has_no_uninstall(self):
        with self.assertRaises(ValueError):
            self.lib.uninstall_app(2)


if __name__ == "__main__":
    unittest.main()
