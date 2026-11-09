"""Tests for the SteamGridDB lookups. Run with: python3 -I tests/test_art.py"""
import logging
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from rom_library import art  # noqa: E402

# SteamGridDB's answer for Planet of Lana II Children of the Leaf, 8 November 2026.
LANA = [{"name": "Planet of Lana 2", "id": 5491708}, {"name": "Planet of Lana", "id": 5287385},
        {"name": "Planet of the Eyes", "id": 6756}]


class SgdbTest(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)

    def artwork(self, results):
        a = art.Artwork(self.cache, logging.getLogger())
        a.get_json = lambda url: {"data": results}
        return a

    def test_sequel_without_its_subtitle(self):
        self.assertEqual(self.artwork(LANA).sgdb_id("Planet of Lana II Children of the Leaf"), 5491708)
        self.assertEqual(self.artwork([]).sgdb_id("Planet of Lana II Children of the Leaf"), 5491708)

    def test_no_intro_article_and_a_version(self):
        zelda = [{"name": "The Legend of Zelda: Ocarina of Time", "id": 1},
                 {"name": "The Legend of Zelda: Majora's Mask", "id": 2}, {"name": "The Legend of Zelda", "id": 3}]
        self.assertEqual(self.artwork(zelda).sgdb_id("Legend of Zelda, The - Ocarina of Time"), 1)
        self.assertEqual(self.artwork(zelda).sgdb_id("The Legend of Zelda Majoras Mask Redux"), 2)

    def test_roman_numeral_and_digit_name_two_games(self):
        mega = [{"name": "Mega Man 2", "id": 2}, {"name": "Mega Man II", "id": 22}]
        a = self.artwork(mega)
        self.assertEqual(a.sgdb_id("Mega Man II"), 22)
        self.assertEqual(a.sgdb_id("Mega Man 2"), 2)

    def test_unknown_name_is_asked_again_at_start(self):
        self.assertIsNone(self.artwork([]).sgdb_id("Planet"))
        self.assertEqual(self.artwork([{"name": "Planet", "id": 7}]).sgdb_id("Planet"), 7)

    def test_thumbnail_comes_from_the_search(self):
        a = self.artwork([{"name": "Zelda", "id": 1}])
        png = "https://cdn2.steamgriddb.com/grid/6176.png"
        a.post_json = lambda url, body: {"data": {"assets": [
            {"url": png, "thumb": "https://cdn2.steamgriddb.com/thumb/6176.png", "width": 920, "height": 430,
             "mime": "image/png", "style": "alternate"}]}}
        self.assertEqual(a.default_sgdb({"name": "Zelda", "art": ["sgdb"]}, "landscape"), png)
        self.assertEqual(a.small(png), "https://cdn2.steamgriddb.com/thumb/6176.png")
        self.assertEqual(a.small("https://cdn2.steamgriddb.com/grid/other.png"), "https://cdn2.steamgriddb.com/grid/other.png")


if __name__ == "__main__":
    unittest.main()
