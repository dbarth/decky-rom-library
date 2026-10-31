import asyncio
import base64
import os

import decky

from rom_library.art import Artwork
from rom_library.library import APPS, Library
from rom_library.processes import Processes

library = None
artwork = None
icons = None
# The refresh of the game facts under way, shared by the callers that ask meanwhile.
refreshing = None

# The plugin's folder under its first name. Decky names a plugin's settings, data and log folders
# after its own folder.
OLD_FOLDER = "rom-tiles"


# Moves what the plugin kept under its first name into the folder Decky gives it now.
def adopt_old_folder(folder):
    old = os.path.join(os.path.dirname(folder), OLD_FOLDER)
    if not os.path.isdir(old) or os.path.isdir(folder) and os.listdir(folder):
        return
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(old):
        os.replace(os.path.join(old, name), os.path.join(folder, name))
    os.rmdir(old)
    decky.logger.info(f"moved {old} to {folder}")


# Decodes the game files that changed, rereads ES-DE's gamelists and checks history.xml.
async def refresh_info():
    global refreshing
    if refreshing is None or refreshing.done():
        async def run():
            try:
                got = await asyncio.to_thread(library.refresh_info)
                decky.logger.info(f"game facts: {got}")
                return got
            except Exception as e:  # noqa: BLE001
                decky.logger.exception(f"game facts: {e}")
                return None
        refreshing = asyncio.get_running_loop().create_task(run())
    return await asyncio.shield(refreshing)


class Plugin:
    async def _main(self):
        global library, artwork, icons
        for folder in (decky.DECKY_PLUGIN_SETTINGS_DIR, decky.DECKY_PLUGIN_RUNTIME_DIR):
            try:
                adopt_old_folder(folder)
            except OSError as e:
                decky.logger.warning(f"{folder}: {e}")
        library = Library(decky.DECKY_PLUGIN_DIR, decky.DECKY_PLUGIN_SETTINGS_DIR, decky.DECKY_USER_HOME,
                          decky.DECKY_PLUGIN_RUNTIME_DIR, decky.logger)
        artwork = Artwork(os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "cache"), decky.logger)
        icons = os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "icons")
        await asyncio.to_thread(library.setup)
        asyncio.get_running_loop().create_task(refresh_info())

    async def _unload(self):
        pass

    # Blocking work runs in a thread so a slow download cannot stall Decky's event loop.
    async def list_systems(self):
        return await asyncio.to_thread(library.system_list)

    async def list_games(self, system):
        def scan():
            if system == APPS:
                return library.app_list()
            s = library.systems()[system]
            return [{
                **{k: g[k] for k in ("path", "file", "name", "appid", "favorite", "missing")},
                # The capsule picked for the tile, else a title screen.
                "thumb": None if g["missing"] else
                library.choice(g["path"], "portrait") or artwork.thumb(library.media_for(s, g)),
            } for g in library.games(system, s)]
        return await asyncio.to_thread(scan)

    # Changes when a game comes into or leaves the system's ROM folder. The library page polls it.
    async def games_stamp(self, system):
        return await asyncio.to_thread(library.stamp, system)

    async def shortcut(self, system, path):
        return await asyncio.to_thread(library.shortcut, system, path)

    async def record_tile(self, path, appid, system, applied):
        await asyncio.to_thread(library.record, path, int(appid), system, applied)

    # Returns, for each tile, the shortcut fields its game now gives and the ones that changed.
    async def sync_plan(self):
        return await asyncio.to_thread(library.sync_plan)

    async def record_applied(self, path, applied):
        await asyncio.to_thread(library.set_applied, path, applied)

    async def forget_tile(self, path, appid=None):
        await asyncio.to_thread(library.forget, path, appid)

    # Returns {id, data, ext} for the image picked for one kind of art, or the default.
    async def artwork(self, system, path, kind):
        def fetch():
            image_id = library.choice(path, kind) or artwork.default(library.media(system, path), kind)
            return {"id": image_id, **artwork.image(image_id)} if image_id else None
        return await asyncio.to_thread(fetch)

    # Returns the facts of a game's page, each when known, and their sources.
    async def info(self, system, path):
        def find():
            try:
                return library.info(system, path)
            except (KeyError, OSError, ValueError) as e:
                decky.logger.warning(f"facts of {path}: {e}")
                return {}
        return await asyncio.to_thread(find)

    # Runs at start and each time the library opens.
    async def refresh_info(self):
        return await refresh_info()

    # Returns {files, size}: the game's files relative to its system's folder, and their size in bytes.
    async def rom_files(self, system, path):
        return await asyncio.to_thread(library.files, system, path)

    async def uninstall(self, system, path):
        await asyncio.to_thread(library.uninstall, system, path)

    # Sends SIGTERM to the emulator of the game Steam runs under appid, and kills the game after 10 s.
    # Returns "quit", "killed", or None when no such game runs.
    async def quit_game(self, appid):
        how = await asyncio.to_thread(Processes().quit, int(appid), log=decky.logger.info)
        decky.logger.info(f"quit game {appid}: {how}")
        return how

    # Moves a game from another folder, such as Downloads, into its system's folder.
    async def import_game(self, system, path):
        return await asyncio.to_thread(library.import_game, system, path)

    # Returns a game's settings in its emulator as {id, values, globals}, or None when the plugin
    # cannot change them. A value of None keeps the global one.
    async def emulator_settings(self, system, path):
        return await asyncio.to_thread(library.emulator_settings, system, path)

    async def set_emulator_setting(self, system, path, key, value):
        await asyncio.to_thread(library.set_emulator_setting, system, path, key, value)

    # Returns what the panel's buttons need: the Downloads folder, whether Loadout is installed, and the
    # ROM folders the user chose. 'roots' is None until the user chooses.
    async def places(self):
        return {
            "downloads": os.path.join(decky.DECKY_USER_HOME, "Downloads"),
            "loadout": os.path.isfile(os.path.join(decky.DECKY_HOME, "plugins", "loadout", "plugin.json")),
            "roots": await asyncio.to_thread(library.roots),
        }

    # Returns the ROM folders the scan finds, as Library in tiles.ts.
    async def find_libraries(self):
        return await asyncio.to_thread(library.find_libraries)

    # Returns where a new library can go, the internal storage first.
    async def new_libraries(self):
        return await asyncio.to_thread(library.new_libraries)

    async def use_library(self, path):
        await asyncio.to_thread(library.use_library, path)

    async def create_library(self, path, include):
        await asyncio.to_thread(library.create_library, path, include)

    async def combine_libraries(self, main, include):
        await asyncio.to_thread(library.combine_libraries, main, include)

    async def get_launcher(self):
        return await asyncio.to_thread(library.launcher)

    async def set_launcher(self, appid):
        await asyncio.to_thread(library.set_launcher, appid)

    # Classifies the shortcuts that are not tiles and says which to give artwork.
    async def apps_plan(self, shortcuts):
        return await asyncio.to_thread(library.apps_plan, shortcuts)

    async def app_art_done(self, appid):
        await asyncio.to_thread(library.app_art_done, int(appid))

    # Says what the plugin knows of a Steam app, for the Quick Access panel.
    async def describe_app(self, appid):
        return await asyncio.to_thread(library.describe, appid)

    # Removes an emulator the hub installed. The caller then removes its Steam shortcut.
    async def uninstall_app(self, appid):
        await asyncio.to_thread(library.uninstall_app, int(appid))

    # Returns an image id for a game that has no title screen to show.
    async def preview(self, system, path):
        def find():
            image_id = library.choice(path, "landscape") or artwork.default(library.media(system, path), "landscape")
            return artwork.small(image_id)
        return await asyncio.to_thread(find)

    async def candidates(self, system, path, kind):
        def find():
            media = library.media(system, path)
            return {
                "current": library.choice(path, kind) or artwork.default(media, kind),
                "items": artwork.candidates(media, kind),
            }
        return await asyncio.to_thread(find)

    async def image(self, image_id):
        return await asyncio.to_thread(artwork.image, image_id)

    async def choose_art(self, path, kind, image_id):
        await asyncio.to_thread(library.choose, path, kind, image_id)

    async def save_icon(self, appid, data):
        def write():
            os.makedirs(icons, exist_ok=True)
            path = os.path.join(icons, f"{int(appid)}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(data))
            return path
        return await asyncio.to_thread(write)

    async def delete_icon(self, appid):
        path = os.path.join(icons, f"{int(appid)}.png")
        if os.path.exists(path):
            os.remove(path)
