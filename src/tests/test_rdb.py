"""Tests for the libretro database reader. Run with: python3 -I tests/test_rdb.py"""
import logging
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from rom_library import rdb  # noqa: E402


def pack(v):
    """Encode the MessagePack subset an .rdb file uses."""
    if isinstance(v, dict):
        return bytes([0x80 | len(v)]) + b"".join(pack(k) + pack(x) for k, x in v.items())
    if isinstance(v, int):
        return bytes([v]) if v < 0x80 else b"\xcd" + v.to_bytes(2, "big")
    if isinstance(v, bytes):
        return b"\xc4" + bytes([len(v)]) + v
    b = v.encode()
    return (bytes([0xA0 | len(b)]) if len(b) < 32 else b"\xd9" + bytes([len(b)])) + b


def database(*entries):
    return b"RARCHDB\0" + bytes(8) + b"".join(pack(e) for e in entries) + b"\xc0" + pack({"count": len(entries)})


class RdbTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        with open(os.path.join(self.dir, "FBNeo - Arcade Games.rdb"), "wb") as f:
            f.write(database(
                {"name": "Ms. Pac-Man", "rom_name": "mspacman.zip", "releaseyear": 1981,
                 "publisher": "Midway / General Computer Corporation", "crc": b"\x01\x02\x03\x04"},
                {"name": "Tomb Raider (Europe)", "rom_name": "Tomb Raider (Europe).iso", "releaseyear": 2014,
                 "publisher": "Square Enix"},
                {"name": "Tomb Raider (Europe)", "rom_name": "Tomb Raider (Europe).iso", "releaseyear": 2021,
                 "publisher": "Square Enix"},
                {"name": "No Facts", "rom_name": "nofacts.zip"},
            ))
        rdb.DIRS = [self.dir]
        self.facts = rdb.Facts("", logging.getLogger())

    def test_by_file_name_then_title(self):
        self.assertEqual(self.facts.lookup("FBNeo - Arcade Games", "mspacman.zip", []),
                         {"year": 1981, "publisher": "Midway / General Computer Corporation"})
        self.assertEqual(self.facts.lookup("FBNeo - Arcade Games", "other.zip", ["Ms. Pac-Man (USA)"])["year"], 1981)
        self.assertEqual(self.facts.lookup("FBNeo - Arcade Games", "nofacts.zip", ["No Facts"]), {})

    def test_releases_that_disagree_give_no_year(self):
        self.assertEqual(self.facts.lookup("FBNeo - Arcade Games", "Tomb Raider (Europe).iso", []),
                         {"publisher": "Square Enix"})

    def test_a_missing_database_gives_nothing(self):
        self.assertEqual(self.facts.lookup("Sega - Saturn", "x.chd", ["X"]), {})


if __name__ == "__main__":
    unittest.main()
