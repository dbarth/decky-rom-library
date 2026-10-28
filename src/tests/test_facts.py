"""Tests for the facts read from game files, FinalBurn Neo, history.xml and ES-DE.
Run with: python3 -I tests/test_facts.py"""
import io
import json
import logging
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
sys.path.insert(0, HERE)

from rom_library import aes, arcade, chd, dreamcast, info, library, n64, names, psp, switch, wii  # noqa: E402
from test_esde import ARM_FILES, Home, touch  # noqa: E402

DISCS = os.path.join(HERE, "fixtures", "discs")
DEFAULTS = os.path.join(HERE, "..", "backend", "defaults")


class ChdTest(unittest.TestCase):
    def test_every_codec_rebuilds_the_iso(self):
        with open(os.path.join(DISCS, "psp.iso"), "rb") as f:
            iso = f.read()
        for codec in ("lzma", "zlib", "huff"):
            with chd.Chd(os.path.join(DISCS, f"psp-{codec}.chd")) as c:
                self.assertEqual(c.codecs[0], codec.encode())
                self.assertEqual(c.read(0, c.size), iso)

    def test_gd_rom_tracks_start_on_multiples_of_4(self):
        with chd.Chd(os.path.join(DISCS, "dreamcast-cdlz.chd")) as c:
            tracks = c.tracks()
            self.assertEqual([(t["track"], t["type"], t["start"]) for t in tracks],
                             [(1, "MODE1_RAW", 0), (2, "AUDIO", 452), (3, "MODE1_RAW", 45004)])
            # Every hunk passes the CRC in the map.
            for i in range(c.hunks):
                c.hunk(i)

    def test_cd_sectors_get_their_ecc_back(self):
        with open(os.path.join(DISCS, "gdi", "track03.bin"), "rb") as f:
            raw = f.read()
        for codec in ("cdlz", "cdzl"):
            with chd.Chd(os.path.join(DISCS, f"dreamcast-{codec}.chd")) as c:
                hunk, frame = divmod(45004, c.hunk_bytes // chd.CD_FRAME)
                kind, _, at, _ = c.read_map()[hunk]
                self.assertLessEqual(kind, chd.CODEC_3)
                c.f.seek(at)
                # chdman dropped the ECC of the first frame of track 3: the reader rebuilds it.
                self.assertTrue(c.f.read(1)[0] & (1 << frame))
                for i in range(2):
                    self.assertEqual(c.frame(45004 + i)[:chd.CD_SECTOR], raw[i * chd.CD_SECTOR:(i + 1) * chd.CD_SECTOR])


class DiscTest(unittest.TestCase):
    def test_psp(self):
        want = {"title": "Test Game®: Portable", "serial": "UCES-00001", "region": "Europe",
                "version": "1.01", "publisher": "Sony Computer Entertainment"}
        for name in ("psp.iso", "psp-lzma.chd", "psp-huff.chd"):
            self.assertEqual(psp.read(os.path.join(DISCS, name)), want)

    def test_dreamcast(self):
        want = {"title": "TEST GAME", "publisher": "TEST COMPANY", "released": "2000-07-14", "region": "Europe",
                "serial": "MK-0000000", "version": "V1.001", "controls": ["Jump Pack", "VMU"]}
        for name in ("dreamcast-cdlz.chd", "dreamcast-cdzl.chd", "gdi/disc.gdi"):
            self.assertEqual(dreamcast.read(os.path.join(DISCS, name)), want)

    def test_wii_rvz(self):
        head = bytearray(0x80)
        head[:6] = b"SMNP01"
        head[7] = 2
        head[0x18:0x1C] = struct.pack(">I", wii.WII_MAGIC)
        head[0x20:0x39] = b"New SUPER MARIO BROS. Wii"
        rvz = b"RVZ\x01" + bytes(0x54) + bytes(head) + bytes(0x100)
        with tempfile.NamedTemporaryFile(suffix=".rvz") as f:
            f.write(rvz)
            f.flush()
            self.assertEqual(wii.read(f.name), {"title": "New SUPER MARIO BROS. Wii", "serial": "SMNP01",
                                                "region": "Europe", "publisher": "Nintendo", "version": "Revision 2"})

    def test_n64_in_a_zip_in_each_byte_order(self):
        head = bytearray(0x40)
        head[:4] = b"\x80\x37\x12\x40"
        head[0x20:0x34] = b"THE LEGEND OF ZELDA ".ljust(20)
        head[0x3B:0x3F] = b"NZLP"
        head[0x3F] = 15
        want = {"title": "THE LEGEND OF ZELDA", "serial": "NZLP", "region": "Europe", "version": "Revision 15"}
        v64 = bytes(b for i in range(0, 0x40, 2) for b in (head[i + 1], head[i]))
        little = bytes(b for i in range(0, 0x40, 4) for b in reversed(head[i:i + 4]))
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in (("zelda.z64", head), ("zelda.v64", v64), ("zelda.n64", little)):
                path = os.path.join(tmp, name + ".zip")
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("readme.txt", "x")
                    z.writestr(name, bytes(data) + bytes(4096))
                self.assertEqual(n64.read(path), want)

    def test_file_name_tags(self):
        self.assertEqual(names.from_file_name("Super Mario Galaxy (Europe, Australia) (En,Fr,De,Es,It).rvz"),
                         {"region": "Europe, Australia",
                          "languages": ["English", "French", "German", "Spanish", "Italian"]})
        self.assertEqual(names.from_file_name("TUNIC [0100DA801624E000][v0][US](nsw2u.in).nsp"), {})


def nsp(keys, nacp):
    """Build an NSP with a ticket and a control NCA whose RomFS holds control.nacp, encrypted as a
    retail one with the given keys."""
    title_key = bytes(range(16))
    rights = bytes.fromhex("0100da801624e0000000000000000000")
    name = b"control.nacp"
    meta = struct.pack("<IIQQII", 0, 0xFFFFFFFF, 0, len(nacp), 0xFFFFFFFF, len(name)) + name
    romfs_head = struct.pack("<10Q", 0x50, 0x50, 0, 0x50, 0, 0x50, 0, 0x50, len(meta), 0x200)
    romfs = (romfs_head + meta).ljust(0x200, b"\0") + nacp
    level = 0x200
    section = (bytes(level) + romfs).ljust((level + len(romfs) + 0x1FF) // 0x200 * 0x200, b"\0")
    start = 0xC00
    upper = bytes(range(8, 0, -1))
    counter = bytes(reversed(upper)) + (start >> 4).to_bytes(8, "big")
    body = aes._run("EVP_aes_128_ctr", title_key, counter, section, encrypt=True)
    header = bytearray(0xC00)
    header[0x200:0x204] = b"NCA3"
    header[0x205] = switch.CONTROL
    header[0x208:0x210] = struct.pack("<Q", start + len(body))
    header[0x210:0x218] = struct.pack("<Q", 0x0100DA801624E000)
    header[0x230:0x240] = rights
    header[0x240:0x248] = struct.pack("<II", start // 0x200, (start + len(body)) // 0x200)
    fs = bytearray(0x200)
    fs[2], fs[3], fs[4] = 0, 3, 3
    fs[8:12] = b"IVFC"
    fs[8 + 0x10 + 0x18 * 5:8 + 0x20 + 0x18 * 5] = struct.pack("<QQ", level, len(romfs))
    fs[0x140:0x148] = upper
    header[0x400:0x600] = fs
    nca = aes.xts(keys["header_key"], bytes(header), 0, encrypt=True) + body
    tik = bytearray(0x2C0)
    tik[0x180:0x190] = aes.ecb(keys["titlekek_00"], title_key, encrypt=True)
    tik[0x2A0:0x2B0] = rights
    files = [("ab12.nca", nca), ("0100da801624e0000000000000000000.tik", bytes(tik))]
    strings = b"".join(n.encode() + b"\0" for n, _ in files)
    entries, offset, at = b"", 0, 0
    for n, data in files:
        entries += struct.pack("<QQII", offset, len(data), at, 0)
        offset += len(data)
        at += len(n) + 1
    return b"PFS0" + struct.pack("<II", len(files), len(strings)) + bytes(4) + entries + strings + b"".join(d for _, d in files)


class SwitchTest(unittest.TestCase):
    def test_nacp_through_a_titlekey(self):
        keys = {"header_key": bytes(range(32, 64)), "titlekek_00": bytes(range(100, 116))}
        nacp = bytearray(0x4000)
        british = 0x300
        nacp[british:british + 5] = b"Tunic"
        nacp[british + 0x200:british + 0x205] = b"Finji"
        nacp[0x302C:0x3030] = struct.pack("<I", 0b1010)
        nacp[0x3040:0x3060] = b"\xff" * 0x20
        nacp[0x3046] = 7
        nacp[0x3060:0x3063] = b"1.0"
        with tempfile.NamedTemporaryFile(suffix=".nsp") as f:
            f.write(nsp(keys, bytes(nacp)))
            f.flush()
            got = switch.read(f.name, "", (keys, {}))
        self.assertEqual(got, {"title": "Tunic", "publisher": "Finji", "version": "1.0",
                               "languages": ["British English", "French"], "ages": {"PEGI": 7},
                               "serial": "0100DA801624E000"})

    def test_keys_come_from_the_emulator_folder(self):
        with tempfile.TemporaryDirectory() as home:
            touch(os.path.join(home, ".local/share/eden/keys/prod.keys"), "header_key = " + "11" * 32 + "\n")
            touch(os.path.join(home, ".local/share/eden/keys/title.keys"), "0100da801624e0000000000000000000 = " + "22" * 16)
            prod, titles = switch.find_keys(home)
        self.assertEqual(prod["header_key"], b"\x11" * 32)
        self.assertEqual(titles["0100da801624e0000000000000000000"], b"\x22" * 16)


HISTORY = """<?xml version="1.0" encoding="UTF-8"?>
<history version="2.89">
  <entry>
    <software><item list="nes" name="galaga" /></software>
    <text>NES cart.:\n\nGalaga (c) 1985 Namco.\n\nThe NES port.\n</text>
  </entry>
  <entry>
    <systems><system name="galaga" /><system name="galagao" /></systems>
    <text>Arcade Video game published 45 years ago:

Galaga (c) 1981 Namco.

Galaga is a single-screen shoot-em-up.

The Boss Galaga has a tractor beam.

- TECHNICAL -

Players: 2
Control: 2-way joystick
Buttons: 1 (FIRE)

- TRIVIA -

Galaga was released in September 1981.

- SOURCES -

A magazine.
</text>
  </entry>
  <entry>
    <systems><system name="galagamw" /></systems>
    <text>Arcade Video game published 45 years ago:

Galaga (c) 1981 Midway.

Licensed by Midway. For more information about the game itself, please see the original Japanese release entry; "Galaga".

- TECHNICAL -

Players: 2
</text>
  </entry>
</history>
"""


class ArcadeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        archive = os.path.join(self.tmp, "history.zip")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("history/history.xml", HISTORY)
        facts = os.path.join(self.tmp, "fbneo.json")
        with open(facts, "w") as f:
            json.dump({"galaga": {"year": "1981", "maker": "Namco", "players": 2, "genres": ["Vertical shooter"],
                                  "vertical": True},
                       "galagamw": {"year": "1981", "maker": "Namco (Midway license)", "parent": "galaga",
                                    "players": 2, "broken": True}}, f)
        self.arcade = arcade.Arcade(facts, os.path.join(self.tmp, "history"), logging.getLogger())
        self.assertEqual(self.arcade.history.index(archive), 2)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_machine(self):
        got = self.arcade.facts("galagao")
        self.assertEqual(got["description"], "Galaga is a single-screen shoot-em-up.\n\nThe Boss Galaga has a tractor beam.")
        self.assertEqual(got["sections"], [("Technical", "Players: 2\nControl: 2-way joystick\nButtons: 1 (FIRE)"),
                                           ("Trivia", "Galaga was released in September 1981.")])
        self.assertEqual(got["controls"], ["2-way joystick", "1 button (FIRE)"])
        self.assertEqual(got["players"], "2")

    def test_clone_gets_the_original_after_its_note(self):
        got = self.arcade.facts("galagamw")
        self.assertEqual(got["description"], "Licensed by Midway.\n\nGalaga is a single-screen shoot-em-up.\n\n"
                                             "The Boss Galaga has a tractor beam.")
        self.assertEqual(got["manufacturer"], "Namco (Midway license)")
        self.assertTrue(got["broken"])

    def test_fbneo_facts_cover_the_dat(self):
        with open(os.path.join(DEFAULTS, "titles", "fbneo.json")) as f:
            titles = json.load(f)
        facts = arcade.Fbneo(os.path.join(DEFAULTS, "facts", "fbneo.json"))
        self.assertEqual({k for k, v in titles.items() if v is not None}, set(facts.load()))
        self.assertEqual(facts.get("marble"), {"board": "System 1", "genres": ["Maze", "Action"],
                                               "maker": "Atari Games", "players": 2, "year": "1984"})


class MergeTest(unittest.TestCase):
    def test_file_first_then_a_date_gains_precision(self):
        got, sources = info.merge([
            ("file", {"publisher": "Nintendo", "released": "1998"}),
            ("esde", {"publisher": "Nintendo of Europe", "released": "1998-12-11", "players": "1"}),
            ("libretro", {"released": "1999", "genre": "Action"}),
        ])
        self.assertEqual(got, {"publisher": "Nintendo", "released": "1998-12-11", "players": "1", "genre": "Action"})
        self.assertEqual(sources, {"publisher": "file", "released": "esde", "players": "esde", "genre": "libretro"})

    def test_esde_dates(self):
        self.assertEqual(info.esde_date("19910206T000000"), "1991-02-06")
        self.assertEqual(info.esde_date("19910101T000000"), "1991")
        self.assertIsNone(info.esde_date(""))


class LibraryInfoTest(unittest.TestCase):
    def setUp(self):
        self.h = Home()
        settings = os.path.join(self.h.root, "settings")
        self.lib = library.Library(DEFAULTS, settings, self.h.home, os.path.join(self.h.root, "runtime"),
                                   logging.getLogger())
        self.lib.esde.bundled = lambda: ARM_FILES
        self.lib.arcade.history.check = lambda: False

    def tearDown(self):
        self.h.cleanup()

    def test_arcade_set(self):
        got = self.lib.info("fbneo", self.h.rom("fbneo/marble.zip"))
        self.assertEqual(got["manufacturer"], "Atari Games")
        self.assertEqual(got["released"], "1984")
        self.assertEqual(got["genre"], "Maze, Action")
        self.assertEqual(got["sources"]["genre"], "fbneo")

    def test_switch_update_version(self):
        base = self.h.rom("switch/TUNIC [0100DA801624E000][v0][US](nsw2u.in).nsp")
        update = self.h.rom("switch/updates/TUNIC [0100DA801624E800][v65536].nsp")
        touch(update, "x")
        versions = {base: "1.0", update: "1.1.2"}
        self.lib.decoded.decode = lambda sid, p: {"serial": "0100DA801624E000", "version": versions[p]}
        self.assertEqual(self.lib.info("switch", base)["version"], "1.0, update 1.1.2")

    def test_file_facts_come_first_and_stay_cached(self):
        shutil.copy(os.path.join(DISCS, "psp.iso"), self.h.rom("psp/LittleBigPlanet (Europe) (PSP) (PSN).iso"))
        path = self.h.rom("psp/LittleBigPlanet (Europe) (PSP) (PSN).iso")
        got = self.lib.info("psp", path)
        self.assertEqual(got["serial"], "UCES-00001")
        self.assertEqual(got["region"], "Europe")
        self.assertEqual(got["sources"]["region"], "file")
        decode = self.lib.decoded.decode
        self.lib.decoded.decode = lambda sid, p: self.fail("decoded twice")
        self.lib.info("psp", path)
        self.lib.decoded.decode = decode
        summary = self.lib.refresh_info()
        # The empty test files of other systems fail to decode, and history.xml is not fetched in tests.
        self.assertGreaterEqual(summary["decoded"], 1)


if __name__ == "__main__":
    unittest.main()
