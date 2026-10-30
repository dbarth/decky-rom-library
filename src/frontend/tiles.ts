import { callable } from "@decky/api";

export interface System {
  id: string;
  name: string;
  collection: string | null;
  // The system takes FinalBurn Neo's arcade sets: its game pages fold the history behind Game Info.
  arcade: boolean;
  // ES-DE's label of the emulator its games start in.
  emulator: string;
  // The extensions of its games, lowercase and without the dot.
  extensions: string[];
  available: boolean;
  reason: string | null;
  games: number;
  tiles: number;
  missing: number;
}

export interface Game {
  path: string;
  file: string;
  name: string;
  appid: number | null;
  // An image id for the game's preview.
  thumb: string | null;
  favorite: boolean;
  // The game has a tile but its ROM is gone.
  missing: boolean;
  // Set on the shortcuts of the Apps tab, which are not tiles.
  kind?: AppKind;
  // The app's id in the SteamOS ARM port's hub, which can uninstall it.
  hub?: string | null;
}

// What a game's page shows of it, each field when known. sources names where each field came from:
// "file", "name", "esde", "fbneo", "history" or "libretro".
export interface Info {
  description?: string;
  // history.xml's sections after the description: [title, text].
  sections?: [string, string][];
  developer?: string;
  publisher?: string;
  // An arcade set's maker, from FinalBurn Neo.
  manufacturer?: string;
  // YYYY, YYYY-MM or YYYY-MM-DD.
  released?: string;
  genre?: string;
  // "2" for up to two players, or ES-DE's "1-4".
  players?: string;
  // ES-DE's rating, from 0 to 1.
  rating?: number;
  region?: string;
  languages?: string[];
  serial?: string;
  version?: string;
  disc?: string | number;
  // The minimum age by rating board.
  ages?: Record<string, number>;
  controls?: string[];
  board?: string;
  broken?: boolean;
  vertical?: boolean;
  media?: string;
  sources?: Record<string, string>;
}

// A game's files, relative to its system's folder, and their size in bytes.
export interface RomFiles {
  files: string[];
  size: number;
}

export type AppKind = "emulator" | "frontend" | "other";

// What the plugin knows of a Steam app: its tile, or its kind of app.
export type AppInfo = { tile: string; system: string } | { kind: AppKind | "launcher"; hub?: string | null };

// A game's settings in its emulator, by key. A null value keeps the global one.
export interface EmulatorSettings {
  id: string;
  values: Record<string, string | null>;
  globals: Record<string, string>;
  emulator: "Dolphin" | "Eden" | "RetroArch";
  // Dolphin's: the disc's console, "wii" or "gc".
  console?: string;
  // Whether the DSU server that sends the handheld's gyroscope runs.
  dsu?: boolean;
  // RetroArch's: whether the game shows an overlay, its bezel.
  overlay?: boolean;
}

// The pseudo system of the shortcuts that are not tiles. Their paths are "app:<appid>".
export const APPS = "apps";

interface AppShortcut {
  appid: number;
  name: string;
  exe: string;
  launch_options: string;
  // The shortcut has a custom capsule.
  art: boolean;
}

interface AppsPlan {
  apps: { appid: number; name: string; kind: AppKind; art: boolean }[];
}

// An image id is an https URL or "file:" and a local path.
export interface Candidate {
  id: string;
  thumb: string | null;
  label: string;
  source: string;
  size: [number, number] | null;
}

export type Kind = "portrait" | "landscape" | "hero" | "logo" | "icon";

export type DriveKind = "internal" | "sd" | "usb";

// A ROM folder the scan found. 'where' is the path from the drive's name or from the home, such
// as MicroSD/Emulation/roms. 'source' names the tool whose settings point there.
export interface Library {
  path: string;
  where: string;
  drive: { kind: DriveKind; name: string };
  // The file system, such as ext4 or exfat. 'links' is false where it holds no symbolic links: the
  // library can join a combined library but cannot hold one.
  fs: string;
  links: boolean;
  source: string | null;
  games: number;
  systems: { id: string; name: string; games: number }[];
}

// Where a new library would go: its drive, the drive's free bytes, and the systems it gets a folder
// for.
export interface NewLibrary {
  path: string;
  drive: { kind: DriveKind; name: string };
  free: number;
  systems: { id: string; name: string }[];
}

// The shortcut fields the plugin sets and keeps in line with ES-DE.
interface Applied {
  name: string;
  exe: string;
  start_dir: string;
  launch_options: string;
}

interface Shortcut extends Applied {
  collection: string | null;
  favorite: boolean;
  // ES-DE's custom collections that hold the game.
  collections: string[];
}

interface SyncItem {
  path: string;
  appid: number;
  missing: boolean;
  want: Applied | null;
  changed: (keyof Applied)[];
  favorite: boolean;
  collections: string[];
  error?: string;
}

interface Art {
  data: string;
  ext: string;
}

export const listSystems = callable<[], System[]>("list_systems");
export const listGames = callable<[system: string], Game[]>("list_games");
export const gamesStamp = callable<[system: string], string>("games_stamp");
const getShortcut = callable<[system: string, path: string], Shortcut>("shortcut");
const recordTile = callable<[path: string, appid: number, system: string, applied: Applied], void>("record_tile");
const getSyncPlan = callable<[], SyncItem[]>("sync_plan");
const recordApplied = callable<[path: string, applied: Applied], void>("record_applied");
const forgetTile = callable<[path: string, appid: number | null], void>("forget_tile");
export const getArtwork = callable<[system: string, path: string, kind: string], Art | null>("artwork");
export const getCandidates = callable<[system: string, path: string, kind: string],
  { current: string | null; items: Candidate[] }>("candidates");
export const getImage = callable<[id: string], Art>("image");
export const getPreview = callable<[system: string, path: string], string | null>("preview");
export const getInfo = callable<[system: string, path: string], Info>("info");
export const refreshInfo = callable<[], unknown>("refresh_info");
export const getRomFiles = callable<[system: string, path: string], RomFiles>("rom_files");
export const uninstallRom = callable<[system: string, path: string], void>("uninstall");
// Sends SIGTERM to the emulator of the game Steam runs under appid, then kills the game after 10 s.
// null when no such game runs.
export const quitGame = callable<[appid: number], "quit" | "killed" | null>("quit_game");
// Moves a game into its system's folder and returns its path there.
export const importGame = callable<[system: string, path: string], string>("import_game");
export const getPlaces = callable<[], { downloads: string; loadout: boolean }>("places");
// Looks in the known places. 'deep' searches every folder of every drive.
export const findLibraries = callable<[deep: boolean], Library[]>("find_libraries");
// Makes the folder the ROM folder ROM Library reads.
export const pickLibrary = callable<[path: string], void>("use_library");
// A new library's creation, with a folder per system and a link per system of the included
// libraries.
// The places a new library can go, the default first: the internal storage, then each card or drive.
export const getNewLibraries = callable<[], NewLibrary[]>("new_libraries");
export const createLibrary = callable<[path: string, include: string[]], void>("create_library");
// Links the systems of the included libraries into the main one.
export const combineLibraries = callable<[main: string, include: string[]], void>("combine_libraries");
export const getEmulatorSettings = callable<[system: string, path: string], EmulatorSettings | null>(
  "emulator_settings");
export const setEmulatorSetting = callable<[system: string, path: string, key: string, value: string | null], void>(
  "set_emulator_setting");
const chooseArt = callable<[path: string, kind: string, id: string], void>("choose_art");
const saveIcon = callable<[appid: number, data: string], string>("save_icon");
const getAppsPlan = callable<[shortcuts: AppShortcut[]], AppsPlan>("apps_plan");
const appArtDone = callable<[appid: number], void>("app_art_done");
const uninstallHubApp = callable<[appid: number], void>("uninstall_app");
export const describeApp = callable<[appid: number], AppInfo | null>("describe_app");
const deleteIcon = callable<[appid: number], void>("delete_icon");
const getLauncher = callable<[], number | null>("get_launcher");
const setLauncher = callable<[appid: number], void>("set_launcher");

// The typed API lacks some of the calls used here and narrows the asset arguments.
const apps = () => SteamClient.Apps as any;

// Asset types of SetCustomArtworkForApp, numbered as the SteamGridDB plugin does.
const ASSET = { portrait: 0, hero: 1, logo: 2, landscape: 3 } as const;
const SIZE = { portrait: [600, 900], landscape: [920, 430], hero: [1920, 620], icon: [256, 256] } as const;
type Framed = keyof typeof SIZE;

interface Loaded {
  art: Art;
  image: HTMLImageElement;
}

// Steam records the playtime of a shortcut. GetPlaytime gives it; the app overview keeps 0.
export async function getPlaytime(appid: number): Promise<{ minutes: number; last: number }> {
  const p = await apps().GetPlaytime(appid);
  return { minutes: p?.nPlaytimeForever ?? 0, last: p?.rtLastTimePlayed ?? 0 };
}

export function tileExists(appid: number): boolean {
  return !!appStore.GetAppOverviewByAppID(appid);
}

// Drops the record of tiles that were removed from Steam by hand.
export async function pruneGames(games: Game[]): Promise<Game[]> {
  const out: Game[] = [];
  for (const g of games) {
    if (g.appid != null && !tileExists(g.appid)) {
      await forgetTile(g.path, g.appid);
      out.push({ ...g, appid: null });
    } else {
      out.push(g);
    }
  }
  return out;
}

async function load(art: Art): Promise<HTMLImageElement> {
  const image = new window.Image();
  image.src = `data:image/${art.ext === "jpg" ? "jpeg" : art.ext};base64,${art.data}`;
  await image.decode();
  return image;
}

function fits(image: HTMLImageElement, w: number, h: number): boolean {
  return Math.abs(image.width / image.height - w / h) / (w / h) < 0.03;
}

// Scales small pixel art by a whole factor first so it stays sharp.
function sharpen(image: HTMLImageElement, scale: number): CanvasImageSource {
  const n = Math.floor(scale);
  if (n < 2) return image;
  const canvas = document.createElement("canvas");
  canvas.width = image.width * n;
  canvas.height = image.height * n;
  const ctx = canvas.getContext("2d")!;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas;
}

// Fits the image in a w x h frame over a blurred, darkened copy of itself.
function frame(image: HTMLImageElement, w: number, h: number): string {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  const cover = Math.max(w / image.width, h / image.height) * 1.1;
  ctx.filter = "blur(24px) brightness(0.55)";
  ctx.drawImage(image, (w - image.width * cover) / 2, (h - image.height * cover) / 2,
    image.width * cover, image.height * cover);
  ctx.filter = "none";
  const scale = Math.min(w / image.width, h / image.height);
  const dw = Math.round(image.width * scale);
  const dh = Math.round(image.height * scale);
  ctx.drawImage(sharpen(image, scale), Math.round((w - dw) / 2), Math.round((h - dh) / 2), dw, dh);
  return canvas.toDataURL("image/png").split(",")[1];
}

function framed(loaded: Loaded, kind: Framed): Art {
  const [w, h] = SIZE[kind];
  if (fits(loaded.image, w, h)) return { data: loaded.art.data, ext: loaded.art.ext };
  return { data: frame(loaded.image, w, h), ext: "png" };
}

// Steam versions all the custom images of an app with the newest file time, in whole seconds.
// A view that reloads an image in the second another one changes keeps the old copy, so the
// last image of a batch is written again in the next second.
async function settle(again: () => Promise<void>): Promise<void> {
  await new Promise((r) => setTimeout(r, 1050 - (Date.now() % 1000)));
  await again();
}

// keepIcon leaves an icon the shortcut already has.
export async function applyArtwork(appid: number, system: string, path: string, keepIcon = false): Promise<void> {
  const got: Partial<Record<string, Loaded>> = {};
  for (const kind of ["portrait", "landscape", "hero", "logo", "icon"]) {
    const art = await getArtwork(system, path, kind);
    if (art) got[kind] = { art, image: await load(art) };
  }
  const first = (...kinds: string[]) => kinds.map((k) => got[k]).find((x): x is Loaded => !!x);
  const fallbacks = {
    portrait: first("portrait", "landscape", "hero"),
    landscape: first("landscape", "hero", "portrait"),
    hero: first("hero", "landscape", "portrait"),
  };
  let last: (() => Promise<void>) | null = null;
  for (const [kind, loaded] of Object.entries(fallbacks) as [keyof typeof fallbacks, Loaded | undefined][]) {
    if (!loaded) continue;
    const { data, ext } = framed(loaded, kind);
    last = () => apps().SetCustomArtworkForApp(appid, data, ext, ASSET[kind]);
    await last();
  }
  const logo = got.logo;
  if (logo) {
    last = () => apps().SetCustomArtworkForApp(appid, logo.art.data, logo.art.ext, ASSET.logo);
    await last();
  }
  if (last) await settle(last);
  const icon = first("icon", "portrait", "landscape");
  if (icon && !keepIcon) {
    const square = icon === got.icon && icon.art.ext === "png" && fits(icon.image, 1, 1);
    const file = await saveIcon(appid, square ? icon.art.data : framed(icon, "icon").data);
    apps().SetShortcutIcon(appid, file);
  }
}

// Sets one kind of a tile's art to the image the user picked, and remembers the pick.
export async function applyImage(appid: number | null, path: string, kind: Kind, id: string): Promise<void> {
  if (appid != null) {
    const art = await getImage(id);
    const loaded = { art, image: await load(art) };
    if (kind === "logo") {
      await apps().SetCustomArtworkForApp(appid, art.data, art.ext, ASSET.logo);
    } else if (kind === "icon") {
      const square = art.ext === "png" && fits(loaded.image, 1, 1);
      apps().SetShortcutIcon(appid, await saveIcon(appid, square ? art.data : framed(loaded, "icon").data));
    } else {
      const { data, ext } = framed(loaded, kind);
      await apps().SetCustomArtworkForApp(appid, data, ext, ASSET[kind]);
    }
  }
  await chooseArt(path, kind, id);
}

async function overview(appid: number): Promise<any> {
  for (let i = 0; i < 30; i++) {
    const found = appStore.GetAppOverviewByAppID(appid);
    if (found) return found;
    await new Promise((r) => setTimeout(r, 100));
  }
  return null;
}

async function addToCollection(appids: number[], name: string): Promise<void> {
  const find = () => collectionStore.userCollections.find((c: any) => c.displayName === name);
  const missing = appids.filter((id) => !find()?.apps.has(id));
  if (!missing.length) return;
  const found = (await Promise.all(missing.map(overview))).filter(Boolean);
  if (!found.length) return;
  if (!find()) await collectionStore.NewUnsavedCollection(name, undefined, []).Save();
  const collection = find();
  if (!collection) return;
  collection.AsDragDropCollection().AddApps(found);
  await collection.Save();
}

// Adds tiles to Steam collections and favorites, and never takes one out.
async function fileTiles(collections: Map<string, number[]>, favorites: number[]): Promise<void> {
  for (const [name, appids] of collections) {
    try {
      await addToCollection(appids, name);
    } catch (e) {
      console.warn("ROM Library: collection", name, e);
    }
  }
  const favorite = collectionStore.GetCollection("favorite");
  const add = favorites.filter((id) => !favorite?.apps.has(id));
  if (add.length) collectionStore.SetAppsAsFavorite(add, true);
}

function group(entries: [string, number][]): Map<string, number[]> {
  const out = new Map<string, number[]>();
  for (const [name, appid] of entries) out.set(name, [...(out.get(name) ?? []), appid]);
  return out;
}

export async function addTile(system: string, game: Game): Promise<number> {
  const s = await getShortcut(system, game.path);
  const appid = Number(await apps().AddShortcut(s.name, s.exe, s.start_dir, s.launch_options));
  if (!appid) throw new Error("Steam did not create the shortcut");
  // Steam names a new shortcut after its executable and may drop the options.
  apps().SetShortcutName(appid, s.name);
  apps().SetShortcutLaunchOptions(appid, s.launch_options);
  await recordTile(game.path, appid, system, s);
  await applyArtwork(appid, system, game.path);
  const names = [s.collection, ...s.collections].filter((c): c is string => !!c);
  await fileTiles(group(names.map((c) => [c, appid])), s.favorite ? [appid] : []);
  return appid;
}

function run(appid: number) {
  const app = appStore.GetAppOverviewByAppID(appid);
  SteamClient.Apps.RunGame(app?.m_gameid ?? String(appid), "", -1, 100);
}

// Asks Steam to end a running app, as its Exit Game does.
export function terminateApp(appid: number) {
  const app = appStore.GetAppOverviewByAppID(appid);
  SteamClient.Apps.TerminateApp(app?.m_gameid ?? String(appid), false);
}

// Runs a tile, or a game without one through a hidden shortcut that takes the game's name and
// command before each run. Steam then tracks the game and gamescope gives it the screen.
export async function playGame(system: string, game: Game): Promise<void> {
  if (game.appid != null && tileExists(game.appid)) return run(game.appid);
  const s = await getShortcut(system, game.path);
  let appid = await getLauncher();
  if (appid == null || !tileExists(appid)) {
    appid = Number(await apps().AddShortcut(s.name, s.exe, s.start_dir, s.launch_options));
    if (!appid) throw new Error("Steam did not create the shortcut");
    await setLauncher(appid);
    await overview(appid);
    if (await collectionsLoaded()) collectionStore.SetAppsAsHidden([appid], true);
  }
  apps().SetShortcutName(appid, s.name);
  apps().SetShortcutExe(appid, s.exe);
  apps().SetShortcutStartDir(appid, s.start_dir);
  apps().SetShortcutLaunchOptions(appid, s.launch_options);
  // Steam applies the changes a little later: a run before that starts the previous game.
  for (let i = 0; i < 15; i++) {
    const d = await details(appid);
    if (d?.strShortcutLaunchOptions === s.launch_options && d?.strDisplayName === s.name) break;
    await new Promise((r) => setTimeout(r, 200));
  }
  run(appid);
  // Steam shows the running game with the shortcut's art: give it the game's, after the launch.
  applyArtwork(appid, system, game.path).catch((e) => console.warn("ROM Library: launcher art", e));
}

// Brings every tile in line with the ROM folders: name, emulator, start folder, launch options,
// favorites and collections. Returns the number of shortcuts changed.
export async function syncTiles(): Promise<number> {
  const plan = await getSyncPlan();
  let changed = 0;
  const collections: [string, number][] = [];
  const favorites: number[] = [];
  for (const item of plan) {
    if (!tileExists(item.appid)) continue;
    if (item.error) console.warn("ROM Library:", item.path, item.error);
    if (!item.want) continue;
    if (item.changed.length) {
      const setters = {
        name: "SetShortcutName", exe: "SetShortcutExe",
        start_dir: "SetShortcutStartDir", launch_options: "SetShortcutLaunchOptions",
      } as const;
      for (const field of item.changed) apps()[setters[field]](item.appid, item.want[field]);
      await recordApplied(item.path, item.want);
      changed++;
    }
    for (const c of item.collections) collections.push([c, item.appid]);
    if (item.favorite) favorites.push(item.appid);
  }
  await fileTiles(group(collections), favorites);
  return changed;
}

// The app type of a non-Steam shortcut in appStore.
const SHORTCUT = 1073741824;

function details(appid: number): Promise<any> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), 3000);
    const handle = SteamClient.Apps.RegisterForAppDetails(appid, (d: any) => {
      clearTimeout(timer);
      handle.unregister();
      resolve(d);
    });
  });
}

// Steam offers a capsule under each image extension it accepts; only one file exists.
export function capsulesOf(appid: number): string[] {
  const app = appStore.GetAppOverviewByAppID(appid);
  return app ? appStore.GetCustomVerticalCapsuleURLs(app) : [];
}

// Steam's collections load a few seconds after its interface, and throw until then.
export function isHidden(appid: number): boolean {
  try {
    return collectionStore.BIsHidden(appid);
  } catch {
    return false;
  }
}

async function collectionsLoaded(): Promise<boolean> {
  for (let i = 0; i < 40; i++) {
    try {
      collectionStore.GetCollection("hidden");
      return true;
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  return false;
}

// Classifies the shortcuts that are not tiles and gives artwork once to the ones without.
export async function syncApps(): Promise<void> {
  const shortcuts: AppShortcut[] = [];
  for (const app of appStore.allApps.filter((a: any) => a.app_type === SHORTCUT)) {
    const d = await details(app.appid);
    if (!d) continue;
    shortcuts.push({
      appid: app.appid,
      name: app.display_name,
      exe: d.strShortcutExe ?? "",
      launch_options: d.strShortcutLaunchOptions ?? "",
      art: appStore.GetCustomVerticalCapsuleURLs(app).length > 0,
    });
  }
  const plan = await getAppsPlan(shortcuts);
  for (const a of plan.apps.filter((x) => x.art)) {
    try {
      const app = appStore.GetAppOverviewByAppID(a.appid);
      await applyArtwork(a.appid, APPS, `app:${a.appid}`, !!(app && appStore.GetIconURLForApp(app)));
    } catch (e) {
      console.warn("ROM Library: app artwork", a.name, e);
    }
    await appArtDone(a.appid);
  }
}

// Hides an app in Steam's library, or shows it there.
export async function setHidden(appid: number, hidden: boolean): Promise<void> {
  if (!(await collectionsLoaded())) throw new Error("Steam's collections did not load");
  collectionStore.SetAppsAsHidden([appid], hidden);
}

async function dropShortcut(appid: number): Promise<void> {
  for (const type of Object.values(ASSET)) {
    try {
      await apps().ClearCustomArtworkForApp(appid, type);
    } catch (e) {
      console.warn("ROM Library: clear artwork", e);
    }
  }
  apps().RemoveShortcut(appid);
  await deleteIcon(appid);
}

export async function removeTile(game: Game): Promise<void> {
  if (game.appid != null) await dropShortcut(game.appid);
  await forgetTile(game.path, game.appid);
}

// Has the hub remove an emulator, then removes its shortcut. Loadout may have removed it first.
export async function uninstallApp(app: Game): Promise<void> {
  await uninstallHubApp(app.appid!);
  if (tileExists(app.appid!)) await dropShortcut(app.appid!);
}
