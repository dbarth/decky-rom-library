"""Tests for the SteamGridDB lookups. Run with: python3 -I tests/test_art.py"""
import json
import logging
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error

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


# Steam's store search for Grand Theft Auto V, 22 November 2026: the Legacy edition is not listed.
GTA = {"items": [{"type": "app", "name": "Grand Theft Auto V Enhanced", "id": 3240220},
                 {"type": "app", "name": "Grand Theft Auto: Vice City – The Definitive Edition", "id": 1546990}]}
HOLLOW = {"items": [{"type": "app", "name": "Hollow Knight: Silksong", "id": 1030300},
                    {"type": "app", "name": "Hollow Knight", "id": 367520}]}


class SteamTest(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache)

    def artwork(self, search, present=()):
        """Answer the store search with search, and serve only the image files named in present."""
        a = art.Artwork(self.cache, logging.getLogger())
        a.asked = []

        def open_url(url, body=None):
            a.asked.append(url)
            if url.startswith(art.STEAM_SEARCH):
                return json.dumps(search).encode()
            if url.rsplit("/", 1)[1] in present:
                return b"image"
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        a.open = open_url
        return a

    def test_the_same_name_first_then_a_longer_one(self):
        self.assertEqual(self.artwork(HOLLOW).steam_id("Hollow Knight"), 367520)
        self.assertEqual(self.artwork(GTA).steam_id("Grand Theft Auto V"), 3240220)
        self.assertIsNone(self.artwork(GTA).steam_id("Grand Theft Auto VI"))

    def test_the_largest_image_on_offer(self):
        a = self.artwork(HOLLOW, present=("library_600x900_2x.jpg", "header.jpg", "logo.png"))
        media = {"name": "Hollow Knight", "art": ["steam", "sgdb"]}
        base = f"{art.STEAM_ASSETS}/367520/"
        self.assertEqual(a.default_steam(media, "portrait"), base + "library_600x900_2x.jpg")
        self.assertEqual(a.default_steam(media, "landscape"), base + "header.jpg")
        self.assertEqual(a.default_steam(media, "logo"), base + "logo.png")
        self.assertIsNone(a.default_steam(media, "hero"))
        self.assertIsNone(a.default_steam(media, "icon"))
        # The app's id is asked once.
        self.assertEqual(sum(u.startswith(art.STEAM_SEARCH) for u in a.asked), 1)

    def test_steam_image_comes_first_in_the_picker(self):
        a = self.artwork(HOLLOW, present=("library_hero.jpg",))
        a.sgdb_assets = lambda *args, **kwargs: [
            {"url": "https://cdn2.steamgriddb.com/hero/1.png", "width": 1920, "height": 620, "style": "alternate"}]
        items = a.candidates({"name": "Hollow Knight", "art": ["steam", "sgdb"], "esde_media": None,
                              "libretro": None}, "hero")
        self.assertEqual([(i["source"], i["id"]) for i in items],
                         [("Steam", f"{art.STEAM_ASSETS}/367520/library_hero.jpg"),
                          ("SGDB", "https://cdn2.steamgriddb.com/hero/1.png")])


if __name__ == "__main__":
    unittest.main()
