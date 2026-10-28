import { toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { useStore } from "./store";
import {
  APPS, EmulatorSettings, Game, Info, Kind, RomFiles, getArtwork, getEmulatorSettings, getImage, getInfo,
  getPlaytime, getPreview, getRomFiles, setEmulatorSetting,
} from "./tiles";

// Data URLs of local images, by id.
const local = new Map<string, Promise<string>>();

export function dataUrl(a: { data: string; ext: string }) {
  return `data:image/${a.ext === "jpg" ? "jpeg" : a.ext};base64,${a.data}`;
}

// Resolves an image id to a URL the page can load: a local file comes as a data URL.
function urlOf(id: string): Promise<string> {
  if (!id.startsWith("file:")) return Promise.resolve(id);
  if (!local.has(id)) local.set(id, getImage(id).then(dataUrl));
  return local.get(id)!;
}

export function useImageUrl(id: string | null): string | null {
  const [url, setUrl] = useState(id && !id.startsWith("file:") ? id : null);
  useEffect(() => {
    if (!id?.startsWith("file:")) {
      setUrl(id);
      return;
    }
    let live = true;
    urlOf(id).then((u) => live && setUrl(u), () => undefined);
    return () => {
      live = false;
    };
  }, [id]);
  return url;
}

// Previews of the games that have no title screen, by ROM path.
const previews = new Map<string, Promise<string | null>>();

export function usePreview(system: string, game: Game): string | null {
  const [id, setId] = useState(game.thumb);
  useEffect(() => {
    if (game.thumb) return;
    if (!previews.has(game.path)) previews.set(game.path, getPreview(system, game.path).catch(() => null));
    let live = true;
    previews.get(game.path)!.then((found) => live && setId(found));
    return () => {
      live = false;
    };
  }, [game.path]);
  return id;
}

// Images of the game page, by ROM path and kind: the lookups, and the URLs they found or null.
const pictures = new Map<string, Promise<string | null>>();
const pictured = new Map<string, string | null>();

// Returns undefined while the image is looked up, then its URL, or null when there is none. An
// image found before shows from the first render. A new pick bumps artVersion and the lookup
// runs again.
export function usePicture(system: string, path: string, kind: Kind): string | null | undefined {
  const key = `${path}\n${kind}`;
  const version = useStore().artVersion;
  const [url, setUrl] = useState(() => pictured.get(key));
  useEffect(() => {
    if (!pictures.has(key)) {
      pictures.set(key, getArtwork(system, path, kind).then((a) => (a ? dataUrl(a) : null), () => null)
        .then((u) => {
          pictured.set(key, u);
          return u;
        }));
    }
    let live = true;
    setUrl(pictured.get(key));
    pictures.get(key)!.then((u) => live && setUrl(u));
    return () => {
      live = false;
    };
  }, [system, path, kind, version]);
  return url;
}

// Facts by ROM path, kept until the library opens again: the backend rereads ES-DE's gamelists and
// the changed files then.
const infos = new Map<string, Promise<Info>>();

export function useInfo(system: string, path: string): Info {
  const [got, setGot] = useState<Info>({});
  useEffect(() => {
    if (system === APPS) return;
    if (!infos.has(path)) infos.set(path, getInfo(system, path).catch(() => ({})));
    let live = true;
    setGot({});
    infos.get(path)!.then((f) => live && setGot(f));
    return () => {
      live = false;
    };
  }, [system, path]);
  return got;
}

export function useRomFiles(system: string, game: Game): RomFiles | null {
  const [got, setGot] = useState<RomFiles | null>(null);
  useEffect(() => {
    setGot(null);
    if (system === APPS || game.missing) return;
    let live = true;
    getRomFiles(system, game.path).then((f) => live && setGot(f), () => undefined);
    return () => {
      live = false;
    };
  }, [system, game.path, game.missing]);
  return got;
}

// The game's settings in its emulator: undefined while they load, null when the plugin cannot change
// them. The setter shows a value at once and puts the old one back if the write fails.
export function useEmulatorSettings(system: string, game: Game):
  [EmulatorSettings | null | undefined, (key: string, value: string | null) => void] {
  const [got, setGot] = useState<EmulatorSettings | null | undefined>(undefined);
  useEffect(() => {
    setGot(undefined);
    if (system === APPS || game.missing) return setGot(null);
    let live = true;
    getEmulatorSettings(system, game.path).then((s) => live && setGot(s), () => live && setGot(null));
    return () => {
      live = false;
    };
  }, [system, game.path, game.missing]);
  const set = (key: string, value: string | null) => {
    const old = got?.values[key] ?? null;
    const put = (v: string | null) => setGot((s) => s && { ...s, values: { ...s.values, [key]: v } });
    put(value);
    setEmulatorSetting(system, game.path, key, value).catch((e) => {
      put(old);
      toaster.toast({ title: "ROM Library", body: `${game.name}: ${e}` });
    });
  };
  return [got, set];
}

export function usePlaytime(appid: number | null): { minutes: number; last: number } | null {
  const [got, setGot] = useState<{ minutes: number; last: number } | null>(null);
  useEffect(() => {
    setGot(null);
    if (appid == null) return;
    let live = true;
    getPlaytime(appid).then((p) => live && setGot(p), () => undefined);
    return () => {
      live = false;
    };
  }, [appid]);
  return got;
}

// Drops the facts read so far: the library reads them again when it opens.
export function forgetInfos() {
  infos.clear();
}

// Drops an image of the game page, which looks it up again.
export function forgetPicture(path: string, kind: Kind) {
  pictures.delete(`${path}\n${kind}`);
  pictured.delete(`${path}\n${kind}`);
}
