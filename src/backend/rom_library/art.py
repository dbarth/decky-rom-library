"""Tile artwork from ES-DE's scraped media, the libretro thumbnails or SteamGridDB."""
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse

from . import web
from .library import read_json, write_json

LIBRETRO = "https://thumbnails.libretro.com"
# SteamGridDB's website API, which needs no key.
SGDB = "https://www.steamgriddb.com/api/public"

# Folders by preference for each kind. Screenshots come before box art.
ESDE_FOLDERS = {
    "portrait": ("titlescreens", "screenshots", "covers", "miximages"),
    "landscape": ("titlescreens", "screenshots", "miximages"),
    "hero": ("fanart", "screenshots", "titlescreens"),
    "logo": ("marquees",),
    "icon": (),
}
ESDE_ALL = ("titlescreens", "screenshots", "covers", "miximages", "fanart")
LIBRETRO_FOLDERS = {
    "portrait": ("Named_Titles", "Named_Snaps", "Named_Boxarts"),
    "landscape": ("Named_Titles", "Named_Snaps", "Named_Boxarts"),
    "hero": ("Named_Snaps", "Named_Titles"),
    "logo": ("Named_Logos",),
    "icon": (),
}
LABELS = {
    "titlescreens": "Title screen", "screenshots": "Screenshot", "covers": "Box art",
    "miximages": "Mix image", "fanart": "Fan art", "marquees": "Marquee",
    "Named_Titles": "Title screen", "Named_Snaps": "Screenshot",
    "Named_Boxarts": "Box art", "Named_Logos": "Logo",
}
# Asset type and the sizes a default may take, most wanted first.
SGDB_ASSETS = {
    "portrait": ("grid", [(600, 900)]),
    "landscape": ("grid", [(920, 430)]),
    "hero": ("hero", [(1920, 620), (3840, 1240)]),
    "logo": ("logo", None),
    "icon": ("icon", None),
}


def simplify(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def ext_of(name):
    return "jpg" if name.lower().endswith((".jpg", ".jpeg")) else "png"


class Artwork:
    def __init__(self, cache_dir, log):
        self.cache = cache_dir
        self.log = log
        self.ids_file = os.path.join(cache_dir, "sgdb-ids.json")
        self.ids = read_json(self.ids_file, {})

    def default(self, media, kind):
        """Return the id of the first image found for one kind, or None.

        An id is an https URL or "file:" and a local path."""
        for source in media["art"]:
            try:
                found = getattr(self, "default_" + source)(media, kind)
            except (OSError, ValueError, KeyError) as e:
                self.log.warning(f"{source} {kind} for {media['name']}: {e}")
                found = None
            if found:
                return found
        return None

    def default_esde(self, media, kind):
        found = self.esde_files(media, ESDE_FOLDERS[kind])
        return found[0][0] if found else None

    def default_libretro(self, media, kind):
        for folder in LIBRETRO_FOLDERS[kind] if media["libretro"] else ():
            url = self.libretro_url(media, folder)
            if self.get(url, missing_ok=True):
                return url
        return None

    def default_sgdb(self, media, kind):
        asset_type, sizes = SGDB_ASSETS[kind]
        assets = [a for a in self.sgdb_assets(media, asset_type, pages=3, sizes=sizes)
                  if kind != "icon" or a["width"] == a["height"]]
        if sizes:
            assets.sort(key=lambda a: sizes.index((a["width"], a["height"])))
        if kind == "logo":
            assets.sort(key=lambda a: a["style"] != "official")
        if kind == "icon":
            assets.sort(key=lambda a: (a["width"] < 128, a["style"] != "official"))
        return assets[0]["url"] if assets else None

    def candidates(self, media, kind):
        """List every image on offer for one kind: [{id, thumb, label, source, size}]."""
        out = []
        folders = ESDE_FOLDERS["logo"] if kind == "logo" else ESDE_ALL
        for path, folder in self.esde_files(media, folders):
            out.append({"id": path, "thumb": None, "label": LABELS[folder], "source": "ES-DE", "size": None})
        if media["libretro"]:
            # A game's icon defaults to SteamGridDB's, but a screenshot is on offer.
            for folder in LIBRETRO_FOLDERS[kind] or LIBRETRO_FOLDERS["landscape"][:2]:
                url = self.libretro_url(media, folder)
                out.append({"id": url, "thumb": url, "label": LABELS[folder], "source": "libretro", "size": None})
        asset_type, sizes = SGDB_ASSETS[kind]
        try:
            assets = self.sgdb_assets(media, asset_type, pages=1)
        except (OSError, ValueError, KeyError) as e:
            self.log.warning(f"sgdb candidates for {media['name']}: {e}")
            assets = []
        if kind == "icon":
            assets = [a for a in assets if a["width"] == a["height"]]
        if sizes:
            assets.sort(key=lambda a: (a["width"], a["height"]) not in sizes)
        for a in assets:
            out.append({
                "id": a["url"],
                "thumb": a.get("thumb") or a["url"],
                "label": a["style"].replace("_", " ").capitalize(),
                "source": "SGDB",
                "size": [a["width"], a["height"]],
            })
        return out

    def thumb(self, media):
        """Return an id for the game's preview: a title screen or a screenshot."""
        found = self.esde_files(media, ("titlescreens", "screenshots"))
        if found:
            return found[0][0]
        return self.libretro_url(media, "Named_Titles") if media["libretro"] else None

    @staticmethod
    def small(image_id):
        """Return SteamGridDB's thumbnail URL for one of its images, else the id."""
        m = re.fullmatch(r"(https://cdn2\.steamgriddb\.com/)\w+/(\w+)\.\w+", image_id or "")
        return f"{m.group(1)}thumb/{m.group(2)}.jpg" if m else image_id

    def image(self, image_id):
        """Return {data, ext} for an id from default() or candidates()."""
        if image_id.startswith("file:"):
            path = image_id[5:]
            if not path.lower().endswith((".png", ".jpg", ".jpeg")):
                raise ValueError(f"not an image: {path}")
            with open(path, "rb") as f:
                data = f.read()
        else:
            data = self.get(image_id)
        return {"data": base64.b64encode(data).decode(), "ext": ext_of(image_id)}

    def esde_files(self, media, folders):
        found = []
        for folder in folders if media["esde_media"] else ():
            for ext in ("png", "jpg"):
                path = os.path.join(media["esde_media"], folder, f"{media['stem']}.{ext}")
                if os.path.isfile(path):
                    found.append(("file:" + path, folder))
        return found

    @staticmethod
    def libretro_url(media, folder):
        # libretro replaces these characters in its file names.
        name = re.sub(r'[&*/:`<>?\\|"]', "_", media["title"])
        return f"{LIBRETRO}/" + urllib.parse.quote(f"{media['libretro']}/{folder}/{name}.png")

    def sgdb_assets(self, media, asset_type, pages, sizes=None):
        game_id = self.sgdb_app_id(media["sgdb_names"]) if media.get("sgdb_names") else self.sgdb_id(media["name"])
        if not game_id:
            return []
        for page in range(pages):
            body = {"asset_type": asset_type, "game_id": [game_id], "page": page}
            assets = self.post_json(f"{SGDB}/search/assets", body)["data"]["assets"]
            if not assets:
                return []
            found = [a for a in assets if self.usable(a, sizes)]
            if found:
                return found
        return []

    @staticmethod
    def usable(asset, sizes):
        if asset.get("is_animated") or asset.get("nsfw") or asset.get("humor") or asset.get("epilepsy"):
            return False
        if asset.get("mime") not in ("image/png", "image/jpeg"):
            return False
        return not sizes or (asset.get("width"), asset.get("height")) in sizes

    def sgdb_id(self, name):
        key = simplify(name)
        if key in self.ids:
            return self.ids[key]
        url = f"{SGDB}/search/autocomplete?term=" + urllib.parse.quote(name)
        results = self.get_json(url).get("data") or []
        # Take an exact match, or a result that extends the name, never a guess.
        match = next((r for r in results if simplify(r["name"]) == key), None)
        if match is None:
            match = next((r for r in results if simplify(r["name"]).startswith(key)), None)
        self.ids[key] = match["id"] if match else None
        write_json(self.ids_file, self.ids)
        return self.ids[key]

    def sgdb_app_id(self, names):
        """Return the id of the first of names SteamGridDB knows exactly, for an app such as an emulator."""
        key = "app:" + simplify(names[-1])
        if key in self.ids:
            return self.ids[key]
        wanted = [simplify(n) for n in names]
        found = {}
        for name in names:
            url = f"{SGDB}/search/autocomplete?term=" + urllib.parse.quote(name)
            for r in self.get_json(url).get("data") or []:
                if simplify(r["name"]) in wanted:
                    found.setdefault(wanted.index(simplify(r["name"])), r["id"])
            if found:
                break
        self.ids[key] = found[min(found)] if found else None
        write_json(self.ids_file, self.ids)
        return self.ids[key]

    def open(self, url, body=None):
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body).encode()
        with web.urlopen(url, body, headers) as r:
            return r.read()

    def get_json(self, url):
        return json.loads(self.open(url))

    def post_json(self, url, body):
        return json.loads(self.open(url, body))

    def get(self, url, missing_ok=False):
        path = os.path.join(self.cache, hashlib.sha1(url.encode()).hexdigest())
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        if os.path.exists(path + ".missing"):
            return None
        os.makedirs(self.cache, exist_ok=True)
        try:
            data = self.open(url)
        except urllib.error.HTTPError as e:
            if missing_ok and e.code == 404:
                open(path + ".missing", "w").close()
                return None
            raise
        with open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
        return data
