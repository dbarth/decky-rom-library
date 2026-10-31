import { openFilePicker, toaster } from "@decky/api";
import type { FileSelectionType } from "@decky/api";
import { Router } from "@decky/ui";
import { useEffect, useReducer } from "react";
import {
  APPS, Game, Kind, System, addTile, applyImage, gamesStamp, importGame, listGames, listSystems, playGame, pruneGames,
  quitGame, removeTile, setHidden, syncApps, syncTiles, terminateApp, tileExists, uninstallApp, uninstallRom,
} from "./tiles";

// FileSelectionType.FILE: a const enum, which vite does not inline.
const PICK_FILE = 0 as FileSelectionType;

// How long a game shows Quitting… before the panel reports that it still runs.
const QUIT_WAIT_MS = 15000;
// How often the library page checks the ROM folder of the tab it shows.
const WATCH_MS = 2000;

interface State {
  systems: System[] | null;
  systemId: string | null;
  games: Record<string, Game[] | undefined>;
  // Progress text of the tiles being added or removed, by ROM path.
  busy: Record<string, string>;
  query: string;
  // The game the game page shows.
  selected: { system: string; path: string } | null;
  // The last game started. Without a tile, it runs as the hidden launcher.
  playing: { system: string; path: string } | null;
  // The full-screen page shows the Apps tab when set.
  appsTab: boolean;
  // Bumps when a tile's art changes, so images Steam serves under the same URL load again.
  artVersion: number;
  // The games whose tile art is being changed, by ROM path.
  artPending: Record<string, boolean>;
  // The game pages show the stats next to Play when set, the game's facts otherwise.
  showStats: boolean;
}

const STATS_KEY = "rom-library.stats";

// Reads a choice kept in Steam's local storage, which a private page can deny.
function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

// The Quick Access panel remounts its content when a dropdown opens, so the
// state lives here and outlives the components.
export const state: State = {
  systems: null, systemId: null, games: {}, busy: {}, query: "", selected: null, playing: null,
  appsTab: false, artVersion: 0, artPending: {}, showStats: stored(STATS_KEY) === "1",
};
const listeners = new Set<() => void>();

export function update(change: Partial<State>) {
  Object.assign(state, change);
  listeners.forEach((l) => l());
}

export function useStore(): State {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    listeners.add(bump);
    return () => {
      listeners.delete(bump);
    };
  }, []);
  return state;
}

// One tile change at a time, so Steam's shortcut list and tiles.json never race.
let queue: Promise<unknown> = Promise.resolve();

function enqueue<T>(job: () => Promise<T>): Promise<T> {
  const run = queue.then(job, job);
  queue = run.catch(() => undefined);
  return run;
}

// Resolves once the work is done and the time has passed: a spinner stays up that long.
function atLeast<T>(ms: number, work: Promise<T>): Promise<T> {
  return Promise.all([work, new Promise((r) => setTimeout(r, ms))]).then(([v]) => v);
}

export function toast(body: string) {
  toaster.toast({ title: "ROM Library", body });
}

export async function loadSystems(): Promise<void> {
  const systems = await listSystems();
  const available = systems.filter((s) => s.available);
  const keep = available.some((s) => s.id === state.systemId);
  update({ systems, systemId: keep ? state.systemId : available[0]?.id ?? null });
}

// Drops the record of tiles removed from Steam by hand.
export async function loadGames(system: string): Promise<void> {
  const listed = await listGames(system);
  const games = system === APPS ? listed.filter((a) => a.appid != null && tileExists(a.appid)) : await pruneGames(listed);
  update({ games: { ...state.games, [system]: games } });
}

// The last stamp of each system's ROM folder. It lasts across tabs: a change made while another tab
// showed reloads the games when the tab shows again.
const stamps: Record<string, string> = {};
let watching = false;

// Reloads the games of the tab on screen and the systems' counts when its ROM folder changes. Polls
// while the library page shows and no game runs.
export function useFolderWatch(system: string | null) {
  useEffect(() => {
    if (!system || system === APPS) return;
    const check = async () => {
      if (watching || Router.MainRunningApp) return;
      watching = true;
      try {
        const stamp = await gamesStamp(system);
        const last = stamps[system];
        stamps[system] = stamp;
        if (last != null && last !== stamp) {
          await loadSystems();
          await loadGames(system);
        }
      } catch {
        // The next check tries again.
      } finally {
        watching = false;
      }
    };
    check();
    const timer = setInterval(check, WATCH_MS);
    return () => clearInterval(timer);
  }, [system]);
}

// Moves a game the user picks in Decky's file picker, which opens on a folder such as Downloads,
// into a system's folder, then lists it. The picker shows the files of the system's extensions.
export async function addGame(system: System, from: string): Promise<void> {
  const picked = await openFilePicker(PICK_FILE, from, true, true, undefined, system.extensions, false, true);
  const name = picked.realpath.split("/").pop();
  try {
    await importGame(system.id, picked.realpath);
    toast(`${name} added to ${system.name}`);
    await Promise.all([loadSystems(), loadGames(system.id)]);
  } catch (e) {
    toast(`${name}: ${e}`);
  }
}

let refreshing: Promise<void> | null = null;

// Reads the ROM folders again and brings the tiles in line with them, at each opening of the panel or the page.
export function refresh(): Promise<void> {
  refreshing ??= reload().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function reload(): Promise<void> {
  await loadSystems();
  try {
    const changed = await enqueue(syncTiles);
    if (changed) toast(`${changed} ${changed > 1 ? "tiles" : "tile"} updated from ES-DE`);
  } catch (e) {
    toast(`Sync with ES-DE: ${e}`);
  }
  if (state.systemId) await loadGames(state.systemId);
  await refreshApps();
}

async function refreshApps(): Promise<void> {
  try {
    await enqueue(syncApps);
  } catch (e) {
    toast(`Apps: ${e}`);
  }
  await loadGames(APPS);
}

export function setShowStats(on: boolean) {
  update({ showStats: on });
  try {
    localStorage.setItem(STATS_KEY, on ? "1" : "0");
  } catch {
    // The choice lasts until Steam restarts.
  }
}

export function selectSystem(id: string) {
  update({ systemId: id });
  if (!state.games[id]) loadGames(id);
}

export function findGame(system: string, path: string): Game | undefined {
  return state.games[system]?.find((g) => g.path === path);
}

function setBusy(path: string, text: string | null) {
  const busy = { ...state.busy };
  if (text == null) delete busy[path];
  else busy[path] = text;
  update({ busy });
}

function replaceGame(system: string, game: Game) {
  // A missing game leaves the list with its tile.
  const games = state.games[system]
    ?.map((g) => (g.path === game.path ? game : g))
    .filter((g) => !(g.missing && g.appid == null));
  update({ games: { ...state.games, [system]: games } });
}

// Adds the game's tile to Steam's library or removes it, in 1 s at least.
export function toggleTile(system: string, game: Game, on: boolean) {
  if (game.path in state.busy) return;
  setBusy(game.path, on ? "Showing in Steam…" : "Hiding from Steam…");
  atLeast(1000, enqueue(async () => {
    if (on) return { ...game, appid: await addTile(system, game) };
    await removeTile(game);
    return { ...game, appid: null };
  }))
    .then((updated) => {
      replaceGame(system, updated);
      toast(`${game.name} ${on ? "added to" : "removed from"} Steam`);
    })
    .catch((e) => toast(`${game.name}: ${e}`))
    .finally(() => setBusy(game.path, null));
}

// Shows an emulator or a front-end in Steam's library, or hides it there, in 1 s at least.
export function showApp(app: Game, on: boolean) {
  if (app.appid == null || app.path in state.busy) return;
  setBusy(app.path, on ? "Showing in Steam…" : "Hiding from Steam…");
  atLeast(1000, setHidden(app.appid, !on))
    .then(() => toast(`${app.name} ${on ? "shown in" : "hidden from"} Steam`))
    .catch((e) => toast(`${app.name}: ${e}`))
    .finally(() => setBusy(app.path, null));
}

// Deletes the game's files, then its tile, in 1 s at least. Resolves true once the game is gone.
export function uninstall(system: string, game: Game): Promise<boolean> {
  if (game.path in state.busy) return Promise.resolve(false);
  setBusy(game.path, "Uninstalling…");
  return atLeast(1000, enqueue(async () => {
    await uninstallRom(system, game.path);
    if (game.appid != null) await removeTile(game);
  }))
    .then(() => {
      update({ games: { ...state.games, [system]: state.games[system]?.filter((g) => g.path !== game.path) } });
      toast(`${game.name} uninstalled`);
      loadSystems();
      return true;
    })
    .catch((e) => {
      toast(`${game.name}: ${e}`);
      return false;
    })
    .finally(() => setBusy(game.path, null));
}

// Has the hub remove an emulator, in 1 s at least. Resolves true once it is gone.
export function uninstallEmulator(app: Game): Promise<boolean> {
  if (app.path in state.busy) return Promise.resolve(false);
  setBusy(app.path, "Uninstalling…");
  return atLeast(1000, enqueue(() => uninstallApp(app)))
    .then(() => {
      update({ games: { ...state.games, [APPS]: state.games[APPS]?.filter((a) => a.path !== app.path) } });
      toast(`${app.name} uninstalled`);
      loadSystems();
      return true;
    })
    .catch((e) => {
      toast(`${app.name}: ${e}`);
      return false;
    })
    .finally(() => setBusy(app.path, null));
}

export function play(system: string, game: Game) {
  update({ playing: { system, path: game.path } });
  setBusy(game.path, "Starting…");
  playGame(system, game)
    .catch((e) => toast(`${game.name}: ${e}`))
    .finally(() => setBusy(game.path, null));
}

// Asks the emulator of the game that runs under appid to quit, through the backend. Steam's own
// Exit Game kills Eden before it saves. Without the game's processes, as in decky-vite, Steam ends
// it. The game shows Quitting… until Steam no longer runs it, for 15 s at most.
export function quit(game: Game, appid: number) {
  setBusy(game.path, "Quitting…");
  const steam = () => {
    try {
      terminateApp(appid);
    } catch (e) {
      toast(`${game.name}: ${e}`);
    }
  };
  quitGame(appid).then((how) => how == null && steam(), steam);
  const started = Date.now();
  const timer = setInterval(() => {
    const runs = Number(Router.MainRunningApp?.appid) === appid;
    if (runs && Date.now() - started < QUIT_WAIT_MS) return;
    clearInterval(timer);
    setBusy(game.path, null);
    if (runs) toast(`${game.name} still runs`);
  }, 500);
}

export const KIND_LABEL: Record<Kind, string> = {
  portrait: "Capsule",
  landscape: "Wide capsule",
  hero: "Background",
  logo: "Logo",
  icon: "Icon",
};

function setArtPending(path: string, on: boolean) {
  const artPending = { ...state.artPending };
  if (on) artPending[path] = true;
  else delete artPending[path];
  update({ artPending });
}

export function pickImage(system: string, path: string, kind: Kind, id: string): Promise<boolean> {
  setArtPending(path, true);
  return enqueue(() => applyImage(findGame(system, path)?.appid ?? null, path, kind, id))
    .then(() => {
      update({ artVersion: state.artVersion + 1 });
      return true;
    })
    .catch((e) => {
      toast(`${KIND_LABEL[kind]}: ${e}`);
      return false;
    })
    .finally(() => setArtPending(path, false));
}
