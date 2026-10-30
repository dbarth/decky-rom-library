import {
  ConfirmModal, DialogButton, Focusable, GamepadButton, Menu, MenuItem, MenuSeparator, ModalRoot, Navigation,
  SteamSpinner, Tabs, TextField, showContextMenu, showModal,
} from "@decky/ui";
import type { GamepadEvent } from "@decky/ui";
import { CSSProperties, ReactNode, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  KIND_LABEL, findGame, loadGames, pickImage, play, refresh, selectSystem, setShowStats, showApp, toggleTile, uninstall,
  uninstallEmulator, update, useFolderWatch, useStore,
} from "./store";
import {
  APPS, AppKind, Candidate, Game, Kind, RomFiles, System, capsulesOf, getCandidates, getImage, isHidden, refreshInfo,
} from "./tiles";
import { GameInfo, MONTHS, factsOf, hasFacts } from "./gameinfo";
import {
  dataUrl, forgetInfos, forgetPicture, useImageUrl, useInfo, usePicture, usePlaytime, usePreview, useRomFiles,
} from "./hooks";
import { CSS } from "./styles";

export const GAMES_ROUTE = "/rom-library";
export const GAME_ROUTE = "/rom-library/game";
export const PROPERTIES_ROUTE = "/rom-library/properties";

const APP_KIND: Record<AppKind, string> = { emulator: "Emulator", frontend: "Front-end", other: "App" };
const RATIO: Record<Kind, number> = { portrait: 600 / 900, landscape: 920 / 430, hero: 1920 / 620, logo: 2, icon: 1 };

// Rounds a size to KB, MB or GB, in steps of 1024 as du -h counts.
export function formatSize(bytes: number): string {
  const units = ["KB", "MB", "GB", "TB"];
  let n = bytes / 1024;
  let i = 0;
  while (n >= 1000 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n < 9.95 ? n.toFixed(1) : Math.round(n)} ${units[i]}`;
}

// Shows an image in a frame of the given shape, over a blurred copy of itself as the tile will.
function Frame({ id, ratio, plain, onError }:
  { id: string | null; ratio: number; plain?: boolean; onError?: () => void }) {
  const url = useImageUrl(id);
  return (
    <div className="rt-frame" style={{ aspectRatio: String(ratio) }}>
      {url && !plain && <img className="rt-backdrop" src={url} loading="lazy" />}
      {url && <img className="rt-fit" src={url} loading="lazy" onError={onError} />}
    </div>
  );
}

// The view box fits the squares, so the icon's bottom edge rests on the title's baseline.
function Logo() {
  return (
    <svg viewBox="3 3 18 18" fill="currentColor">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  );
}

// Marks a game with a Steam tile: the logo, or a warning when its ROM is gone.
function TileBadge({ missing }: { missing?: boolean }) {
  return missing
    ? <span className="rt-badge">ROM missing</span>
    : <span className="rt-badge rt-in-steam" title="In Steam"><Logo /></span>;
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="6.5" cy="6.5" r="5" /><path d="M10.5 10.5 15 15" />
    </svg>
  );
}

// The page with the plugin's own bar in the row of Steam's status bar, so it never passes for the
// Steam library. A bare page, such as a game's, runs its art up there instead.
export function Page({ children, bare }: { children: ReactNode; bare?: boolean }) {
  const s = useStore();
  return (
    <div className="rt-page">
      <style>{CSS}</style>
      {!bare && (
        <Focusable className="rt-bar" flow-children="row">
          <div className="rt-brand"><Logo />ROM Library</div>
          <div className="rt-search">
            <SearchIcon />
            <TextField value={s.query} onChange={(e) => search(e.target.value)}
              {...({ placeholder: "Search ROMs..." } as object)} />
          </div>
        </Focusable>
      )}
      <div className="rt-body">{children}</div>
    </div>
  );
}

function search(query: string) {
  update({ query });
}

// Content outside the tabs, which scroll and pad their own.
function Scroll({ children }: { children: ReactNode }) {
  return <div className="rt-scroll"><div className="rt-content">{children}</div></div>;
}

function Tab({ children }: { children: ReactNode }) {
  return <div className="rt-tab">{children}</div>;
}

// Opens the page where it was left.
export function openGames() {
  Navigation.Navigate(GAMES_ROUTE);
  Navigation.CloseSideMenus();
}

// Steam serves a changed capsule under the same URL.
function capsules(appid: number, version: number): string[] {
  return capsulesOf(appid).map((u) => `${u}${u.includes("?") ? "&" : "?"}rt=${version}`);
}

function openGame(system: string, path: string) {
  update({ selected: { system, path } });
  Navigation.Navigate(GAME_ROUTE);
}

function GameCard({ system, game, sub }: { system: string; game: Game; sub?: string }) {
  const s = useStore();
  const busy = s.busy[game.path];
  const [broken, setBroken] = useState(false);
  const [tried, setTried] = useState(0);
  const thumb = usePreview(system, game);
  const inSteam = game.appid != null;
  // A tile shows its Steam capsule, the title screen until it has one.
  const urls = inSteam ? capsules(game.appid!, s.artVersion) : [];
  const capsule = urls[tried] ?? null;
  const image = capsule ?? (broken ? null : thumb);
  const media = useId();
  return (
    <Focusable
      className="rt-card rt-capsule"
      focusClassName="rt-focus"
      {...({ focusRingSizeElementID: media } as object)}
      onActivate={() => openGame(system, game.path)}
      onOKActionDescription="Open"
      onSecondaryButton={() => !game.missing && toggleTile(system, game, !inSteam)}
      onSecondaryActionDescription={game.missing ? undefined : inSteam ? "Hide from Steam" : "Show in Steam"}
    >
      <div className="rt-media" id={media}>
        <Frame key={image ?? ""} id={image} ratio={RATIO.portrait}
          onError={() => (capsule ? setTried(tried + 1) : setBroken(true))} />
        {inSteam && <TileBadge missing={game.missing} />}
        {busy && <div className="rt-tile-busy"><Spinner /></div>}
      </div>
      <div className="rt-name">{game.name}</div>
      {sub && <div className="rt-sub">{sub}</div>}
    </Focusable>
  );
}

function GameGrid({ system }: { system: System }) {
  const games = useStore().games[system.id];
  if (!games) return <SteamSpinner />;
  if (games.length === 0) return <div className="rt-empty">No game.</div>;
  return (
    <Focusable className="rt-grid rt-games" flow-children="grid">
      {games.map((g) => <GameCard key={g.path} system={system.id} game={g} />)}
    </Focusable>
  );
}

// The games of every system whose name or file holds the query.
function Results() {
  const s = useStore();
  const available = (s.systems ?? []).filter((x) => x.available);
  useEffect(() => {
    for (const x of available) if (!s.games[x.id]) loadGames(x.id);
  }, [available.length]);
  const q = s.query.trim().toLowerCase();
  const hits = useMemo(() => available.flatMap((x) => (s.games[x.id] ?? [])
    .filter((g) => g.name.toLowerCase().includes(q) || g.file.toLowerCase().includes(q))
    .map((g) => ({ system: x, game: g }))), [s.games, q, available.length]);
  const loading = available.some((x) => !s.games[x.id]);
  if (hits.length === 0) return loading ? <SteamSpinner /> : <div className="rt-empty">Nothing matches.</div>;
  return (
    <Focusable className="rt-grid rt-games" flow-children="grid">
      {hits.map(({ system, game }) => (
        <GameCard key={game.path} system={system.id} game={game} sub={system.name} />
      ))}
    </Focusable>
  );
}

// An emulator or a front-end, marked like a tile while Steam's library shows it.
function AppCard({ app }: { app: Game }) {
  const busy = useStore().busy[app.path];
  const [tried, setTried] = useState(0);
  const capsules = app.appid != null ? capsulesOf(app.appid) : [];
  const shown = app.appid != null && !isHidden(app.appid);
  const media = useId();
  return (
    <Focusable className="rt-card rt-capsule" focusClassName="rt-focus" {...({ focusRingSizeElementID: media } as object)}
      onActivate={() => openGame(APPS, app.path)} onOKActionDescription="Open"
      onSecondaryButton={() => showApp(app, !shown)}
      onSecondaryActionDescription={shown ? "Hide from Steam" : "Show in Steam"}>
      <div className="rt-media" id={media}>
        <Frame key={tried} id={capsules[tried] ?? null} ratio={RATIO.portrait} onError={() => setTried(tried + 1)} />
        {shown && <TileBadge />}
        {busy && <div className="rt-tile-busy"><Spinner /></div>}
      </div>
      <div className="rt-name">{app.name}</div>
    </Focusable>
  );
}

function AppGrid() {
  const apps = useStore().games[APPS];
  if (!apps) return <SteamSpinner />;
  if (apps.length === 0) return <div className="rt-empty">No app besides the tiles.</div>;
  return (
    <Focusable className="rt-grid rt-games" flow-children="grid">
      {apps.map((a) => <AppCard key={a.path} app={a} />)}
    </Focusable>
  );
}

export function GamesPage() {
  const s = useStore();
  useEffect(() => {
    refresh();
    forgetInfos();
    refreshInfo().catch(() => undefined);
  }, []);
  const available = (s.systems ?? []).filter((x) => x.available);
  useFolderWatch(s.appsTab ? null : s.systemId ?? available[0]?.id ?? null);
  let body: ReactNode;
  if (!s.systems) body = <SteamSpinner />;
  else if (s.query.trim()) body = <Scroll><Results /></Scroll>;
  else if (available.length === 0) body = <Scroll><div className="rt-empty">No system has both ROMs and an emulator.</div></Scroll>;
  else body = (
    <Tabs
      activeTab={s.appsTab ? APPS : s.systemId ?? available[0].id}
      onShowTab={(id: string) => {
        update({ appsTab: id === APPS });
        if (id !== APPS) selectSystem(id);
      }}
      autoFocusContents
      tabs={[
        ...available.map((sys) => ({ id: sys.id, title: sys.name, content: <Tab><GameGrid system={sys} /></Tab> })),
        { id: APPS, title: "Emulators", content: <Tab><AppGrid /></Tab> },
      ]}
    />
  );
  return <Page>{body}</Page>;
}

const SLIDE_MS = 10000;
// The slides are large wide images: SteamGridDB's heroes and fan art. Screenshots and title
// screens are 4:3 and a few hundred pixels wide.
const SLIDE_WIDTH = 1280;
const SLIDE_RATIO = 1.5;

function isSlide(width: number, height: number): boolean {
  return width >= SLIDE_WIDTH && width / height >= SLIDE_RATIO;
}

// Measures a picture inside the black or transparent bands of its file, sampled 480 pixels wide. A
// row or a column belongs to a band while under 2% of its pixels show. Returns the inset that crops
// the bands and the size of what is left, in the picture's pixels.
function bands(img: HTMLImageElement): { box: string | null; width: number; height: number } {
  const full = { box: null, width: img.naturalWidth, height: img.naturalHeight };
  const w = Math.min(img.naturalWidth, 480);
  const h = Math.max(1, Math.round((img.naturalHeight * w) / img.naturalWidth));
  const ctx = Object.assign(document.createElement("canvas"), { width: w, height: h })
    .getContext("2d", { willReadFrequently: true });
  if (!ctx) return full;
  ctx.drawImage(img, 0, 0, w, h);
  const px = ctx.getImageData(0, 0, w, h).data;
  const shows = (x: number, y: number) => {
    const i = (y * w + x) * 4;
    return px[i + 3] > 32 && px[i] + px[i + 1] + px[i + 2] > 60;
  };
  const count = (n: number, at: (k: number) => boolean) => {
    let c = 0;
    for (let k = 0; k < n; k++) c += at(k) ? 1 : 0;
    return c;
  };
  const row = (y: number) => count(w, (x) => shows(x, y)) > w * 0.02;
  const column = (x: number) => count(h, (y) => shows(x, y)) > h * 0.02;
  let [top, bottom, left, right] = [0, h - 1, 0, w - 1];
  while (top < bottom && !row(top)) top++;
  while (bottom > top && !row(bottom)) bottom--;
  while (left < right && !column(left)) left++;
  while (right > left && !column(right)) right--;
  const [inW, inH] = [right - left + 1, bottom - top + 1];
  // A dark picture keeps its frame: cropping it would leave too little.
  if ((inW === w && inH === h) || inW < w * 0.3 || inH < h * 0.3) return full;
  const pc = (n: number, of: number) => `${((n * 100) / of).toFixed(2)}%`;
  return {
    box: `inset(${pc(top, h)} ${pc(w - 1 - right, w)} ${pc(h - 1 - bottom, h)} ${pc(left, w)})`,
    width: Math.round((img.naturalWidth * inW) / w), height: Math.round((img.naturalHeight * inH) / h),
  };
}

interface Slide {
  url: string;
  // The object-view-box that crops the bands of the file.
  box: string | null;
  width: number;
  height: number;
}

// Resolves once the picture has loaded and its bands are measured, so that it fades in whole.
function loadSlide(url: string): Promise<Slide> {
  return new Promise((ok, fail) => {
    const img = new Image();
    img.onload = () => {
      try {
        ok({ url, ...bands(img) });
      } catch {
        ok({ url, box: null, width: img.naturalWidth, height: img.naturalHeight });
      }
    };
    img.onerror = fail;
    img.src = url;
  });
}

// The hero art, then every 10 s the next large image on offer for the game, faded in over the last.
// The images on offer load at the first change: a page left within 10 s asks for none. The backend
// sends each one, so that the page can read its pixels and crop its bands.
function Hero({ system, path, first }: { system: string; path: string; first: string | null | undefined }) {
  const [slides, setSlides] = useState<(Slide & { n: number })[]>([]);
  useEffect(() => {
    if (first === undefined) return;
    setSlides([]);
    let live = true;
    let timer = 0;
    if (first) loadSlide(first).then((x) => live && setSlides([{ ...x, n: 0 }]), () => undefined);
    // The images after the hero, then the hero again when it is large.
    let order: string[] | null = null;
    let at = 0;
    let n = 0;
    let last = first;
    const urls = new Map<string, Promise<string>>();
    const urlOfSlide = (id: string) => {
      if (id === first) return Promise.resolve(id);
      if (!urls.has(id)) urls.set(id, getImage(id).then(dataUrl));
      return urls.get(id)!;
    };
    const next = async () => {
      if (!order) {
        const key = `${path}\nhero`;
        if (!offers.has(key)) offers.set(key, getCandidates(system, path, "hero"));
        const offer = await offers.get(key)!.catch(() => {
          offers.delete(key);
          return null;
        });
        const others = (offer?.items ?? [])
          .filter((c) => c.id !== offer?.current && (!c.size || isSlide(c.size[0], c.size[1]))).map((c) => c.id);
        order = [...others, ...(first ? [first] : [])];
      }
      while (live && order.some((id) => id !== last)) {
        at %= order.length;
        if (order[at] === last) {
          at++;
          continue;
        }
        try {
          const slide = await loadSlide(await urlOfSlide(order[at]));
          if (!isSlide(slide.width, slide.height)) throw new Error("small");
          if (!live) return;
          const shown = { ...slide, n: ++n };
          last = order[at++];
          setSlides((all) => [...all.slice(-1), shown]);
          break;
        } catch {
          urls.delete(order[at]);
          order.splice(at, 1);
        }
      }
      if (live && order.length > 1) timer = window.setTimeout(next, SLIDE_MS);
    };
    timer = window.setTimeout(next, SLIDE_MS);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [system, path, first]);
  // A slide covers the one under it once faded in: the one under goes, so that it never shows
  // through the transparent parts of the next.
  return (
    <>
      {slides.map((x) => (
        <img key={x.n} className={x.n ? "rt-slide" : undefined} src={x.url}
          style={x.box ? ({ objectViewBox: x.box } as CSSProperties) : undefined}
          onAnimationEnd={() => setSlides((all) => all.filter((y) => y.n >= x.n))} />
      ))}
    </>
  );
}

function PlayIcon() {
  return <svg viewBox="0 0 16 16" fill="currentColor"><path d="M3 1.5v13l11-6.5z" /></svg>;
}

export function Spinner() {
  return <span className="rt-spin" />;
}

// Asks before deleting the game's files, then goes back to the grid once they are gone: 2 pages
// back from the Properties.
export function confirmUninstall(system: string, game: Game, files: RomFiles, where: string, pages = 1) {
  const size = formatSize(files.size);
  const [first, ...rest] = files.files;
  const what = rest.length ? `${files.files.length} files, ${size},` : `${first}, ${size},`;
  const shown = rest.length ? files.files.slice(0, 8) : [];
  showModal(
    <ConfirmModal strTitle={`Uninstall ${game.name}?`} strOKButtonText="Uninstall" bDestructiveWarning
      strDescription={
        <div className="rt-modal">
          <style>{CSS}</style>
          This deletes {what} from the {where} folder.{game.appid != null && " It removes the tile from Steam."}
          {shown.length > 0 && (
            <div className="rt-files">
              {shown.map((f) => <div key={f}>{f}</div>)}
              {files.files.length > shown.length && <div>and {files.files.length - shown.length} more</div>}
            </div>
          )}
        </div>
      }
      onOK={() => uninstall(system, game).then((done) => {
        for (let i = 0; done && i < pages; i++) Navigation.NavigateBack();
      })} />,
  );
}

// A solid gear of 8 teeth between radii 8.4 and 11, around a hole of radius 3.4.
function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d={"M9.54 3.97L9.9 1.2A11 11 0 0 1 14.1 1.2L14.46 3.97A8.4 8.4 0 0 1 15.94 4.58L18.15 2.88"
        + "A11 11 0 0 1 21.12 5.85L19.42 8.06A8.4 8.4 0 0 1 20.03 9.54L22.8 9.9A11 11 0 0 1 22.8 14.1L20.03 14.46"
        + "A8.4 8.4 0 0 1 19.42 15.94L21.12 18.15A11 11 0 0 1 18.15 21.12L15.94 19.42A8.4 8.4 0 0 1 14.46 20.03"
        + "L14.1 22.8A11 11 0 0 1 9.9 22.8L9.54 20.03A8.4 8.4 0 0 1 8.06 19.42L5.85 21.12A11 11 0 0 1 2.88 18.15"
        + "L4.58 15.94A8.4 8.4 0 0 1 3.97 14.46L1.2 14.1A11 11 0 0 1 1.2 9.9L3.97 9.54A8.4 8.4 0 0 1 4.58 8.06"
        + "L2.88 5.85A11 11 0 0 1 5.85 2.88L8.06 4.58A8.4 8.4 0 0 1 9.54 3.97Z"
        + "M15.4 12A3.4 3.4 0 1 0 8.6 12A3.4 3.4 0 1 0 15.4 12Z"} />
    </svg>
  );
}

// A picture in a 1.75 frame, with a solid sun and two solid peaks to match the gear.
function ImageIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d={"M3.5 3.5H20.5A2.5 2.5 0 0 1 23 6V18A2.5 2.5 0 0 1 20.5 20.5H3.5A2.5 2.5 0 0 1 1 18V6"
        + "A2.5 2.5 0 0 1 3.5 3.5Z"
        + "M3.75 5.25H20.25A1 1 0 0 1 21.25 6.25V17.75A1 1 0 0 1 20.25 18.75H3.75A1 1 0 0 1 2.75 17.75V6.25"
        + "A1 1 0 0 1 3.75 5.25Z"
        + "M10 9.5A2 2 0 1 0 6 9.5A2 2 0 1 0 10 9.5Z"
        + "M4.5 17.25L10 11L13.5 14.75L16 12L19.5 17.25Z"} />
    </svg>
  );
}

// Three solid bars, for the stats.
function ChartIcon() {
  return <svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 13h5v9H2ZM9.5 2h5v20h-5ZM17 8h5v14h-5Z" /></svg>;
}

// A solid disc with an i cut out of it, for the game's facts.
function InfoIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d={"M12 1a11 11 0 1 1 0 22a11 11 0 1 1 0-22ZM10.6 10h2.8v8.5h-2.8Z"
        + "M13.6 6.9a1.6 1.6 0 1 1-3.2 0a1.6 1.6 0 1 1 3.2 0Z"} />
    </svg>
  );
}

// Writes a day as Steam does: "Today", "Yesterday", "Oct 20" or "Oct 20, 2025".
function formatDay(time: number): string {
  if (!time) return "Never";
  const day = new Date(time * 1000);
  const today = new Date();
  const days = Math.round((new Date(today.toDateString()).getTime() - new Date(day.toDateString()).getTime()) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  const date = `${MONTHS[day.getMonth()]} ${day.getDate()}`;
  return day.getFullYear() === today.getFullYear() ? date : `${date}, ${day.getFullYear()}`;
}

// Writes a playtime as Steam does: "28 minutes" under an hour, then "4.5 hours".
function formatPlaytime(minutes: number): string {
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
  const hours = Math.round(minutes / 6) / 10;
  return `${hours} ${hours === 1 ? "hour" : "hours"}`;
}

// Asks before the hub removes the app, then goes back to the grid once it is gone.
function confirmAppUninstall(app: Game) {
  showModal(
    <ConfirmModal strTitle={`Uninstall ${app.name}?`} strOKButtonText="Uninstall" bDestructiveWarning
      strDescription={`This removes ${app.name} and its Steam shortcut. Its settings and saves stay.`}
      onOK={() => uninstallEmulator(app).then((done) => done && Navigation.NavigateBack())} />,
  );
}

// The menu of an emulator or a front-end: start it alone, to change its settings. The hub's apps
// can be uninstalled.
function appMenu(at: EventTarget | null, app: Game) {
  showContextMenu(
    <Menu label="Emulator">
      <MenuItem onSelected={() => play(APPS, app)}>Launch {app.name}</MenuItem>
      {app.hub && <MenuSeparator />}
      {app.hub && <MenuItem tone="destructive" onSelected={() => confirmAppUninstall(app)}>Uninstall…</MenuItem>}
    </Menu>,
    at ?? window,
  );
}

// L1 and R1 step through the games of the grid.
const BUMPERS: Record<number, number> = { [GamepadButton.BUMPER_LEFT]: -1, [GamepadButton.BUMPER_RIGHT]: 1 };

// The page of one game, laid out as Steam's: its wide art, Play and the facts.
function GameView({ system, game }: { system: string; game: Game }) {
  const s = useStore();
  const isApp = system === APPS;
  // An app's button shows it in Steam's library or hides it there.
  const shown = isApp && game.appid != null && !isHidden(game.appid);
  const inSteam = isApp ? shown : game.appid != null;
  const hero = usePicture(system, game.path, "hero");
  // The image button spins while a new image is applied.
  const refreshing = !!s.artPending[game.path];
  const f = useInfo(system, game.path);
  const files = useRomFiles(system, game);
  const busy = s.busy[game.path];
  // The main button spins for its own action: Play while the game starts, an app's button while
  // it shows or hides the app. The gear spins for the others.
  const mainBusy = !!busy && (isApp ? !busy.startsWith("Uninstalling") : busy.startsWith("Starting"));
  const sys = s.systems?.find((x) => x.id === system);
  // An arcade game's page shows two lines of its history. Game Info slides the rest up as a second
  // screen, which stays mounted until it has slid back down.
  const facts = factsOf(f);
  const arcade = !isApp && !!sys?.arcade && hasFacts(facts);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const top = useRef<HTMLDivElement>(null);
  const more = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) first.current?.focus();
    else if (mounted) more.current?.focus();
  }, [open]);
  // Up from the top of Game Info lands on the first screen, which slides back.
  useEffect(() => {
    const el = top.current;
    const close = () => setOpen(false);
    el?.addEventListener("focusin", close);
    return () => el?.removeEventListener("focusin", close);
  }, []);
  // Play takes the focus when the page opens. On an app's page the gear does: it leads to the
  // launcher, and showing the app in Steam's library stays a choice.
  const main = useRef<HTMLDivElement>(null);
  const gear = useRef<HTMLDivElement>(null);
  useEffect(() => {
    (isApp ? gear : main).current?.focus();
  }, [game.path]);
  // The teaser takes the strip's middle column, the stats' box. It stays out of the buttons' row so
  // that down from Play reaches Game Info: its place is measured.
  const strip = useRef<HTMLDivElement>(null);
  const [middle, setMiddle] = useState<CSSProperties>();
  useLayoutEffect(() => {
    const stats = strip.current?.querySelector(".rt-stats");
    if (!arcade || !strip.current || !stats) return;
    const from = strip.current;
    const place = () => {
      const box = stats.getBoundingClientRect();
      setMiddle({ marginLeft: box.left - from.getBoundingClientRect().left, width: box.width });
    };
    place();
    const watch = new ResizeObserver(place);
    watch.observe(stats);
    return () => watch.disconnect();
  }, [arcade]);
  // The page shows the previous or next game in the grid's order. B goes back to the grid.
  const step = (e: GamepadEvent) => {
    const games = s.games[system] ?? [];
    const next = BUMPERS[e.detail.button] && games[games.findIndex((g) => g.path === game.path) + BUMPERS[e.detail.button]];
    if (next) update({ selected: { system, path: next.path } });
  };
  const played = usePlaytime(game.appid);
  // The first tool button switches every game page between the stats and the game's facts.
  const stats: [string, ReactNode][] = s.showStats ? [
    ["Last Played", played && formatDay(played.last)],
    ["Play Time", played?.minutes ? formatPlaytime(played.minutes) : "No play time yet"],
  ] : isApp ? [["Kind", APP_KIND[game.kind ?? "other"]]] : [
    ["Released", f.released?.slice(0, 4)],
    ["Publisher", f.publisher ?? f.developer ?? f.manufacturer],
    ["Size", files && formatSize(files.size)],
  ];
  return (
    <Focusable className="rt-pages" flow-children="column" onButtonDown={step}>
      <div className={`rt-track${open ? " rt-open" : ""}`}
        onTransitionEnd={(e) => e.target === e.currentTarget && !open && setMounted(false)}>
        <div ref={top} className="rt-game">
          <div className="rt-hero">
            <Hero system={system} path={game.path} first={hero} />
            <div className="rt-headline">
              <div className="rt-title">{game.name}</div>
              {inSteam && <span className="rt-steam">In Steam<Logo /></span>}
            </div>
          </div>
          <div ref={strip} className="rt-strip">
            <Focusable className="rt-actions" flow-children="row">
              {isApp ? (
                <DialogButton ref={main} className={`rt-act rt-big${mainBusy ? " rt-pending" : ""}`}
                  onClick={() => showApp(game, !shown)}>
                  <span className="rt-text"><Logo />{shown ? "Hide from Steam" : "Show in Steam"}</span>
                  {mainBusy && <Spinner />}
                </DialogButton>
              ) : (
                <DialogButton ref={main} className={`rt-act rt-big rt-play${mainBusy ? " rt-pending" : ""}`}
                  disabled={game.missing} onClick={() => play(system, game)}>
                  <span className="rt-text"><PlayIcon />{game.missing ? "ROM missing" : "Play"}</span>
                  {mainBusy && <Spinner />}
                </DialogButton>
              )}
              <dl className="rt-stats">
                {stats.filter(([, v]) => v).map(([k, v]) => <div key={k} className="rt-stat"><dt>{k}</dt><dd>{v}</dd></div>)}
              </dl>
              <div className="rt-tools">
                <Focusable className="rt-radio" flow-children="row">
                  {[false, true].map((on) => (
                    <DialogButton key={String(on)} className={`rt-act rt-icon${s.showStats === on ? " rt-on" : ""}`}
                      onClick={() => setShowStats(on)} onOKActionDescription={on ? "Show stats" : "Show info"}>
                      {on ? <ChartIcon /> : <InfoIcon />}
                    </DialogButton>
                  ))}
                </Focusable>
                <DialogButton className={`rt-act rt-icon${refreshing ? " rt-pending" : ""}`}
                  onClick={() => customize(system, game.path)}>
                  <span className="rt-text"><ImageIcon /></span>
                  {refreshing && <Spinner />}
                </DialogButton>
                <DialogButton ref={gear} className={`rt-act rt-icon${busy && !mainBusy ? " rt-pending" : ""}`}
                  disabled={!!busy} onClick={(e) => (isApp ? appMenu(e.currentTarget, game)
                    : Navigation.Navigate(PROPERTIES_ROUTE))}>
                  <span className="rt-text"><GearIcon /></span>
                  {busy && !mainBusy && <Spinner />}
                </DialogButton>
              </div>
            </Focusable>
          </div>
          {arcade && (
            <div className="rt-teaser" style={middle}>
              {facts.paragraphs.length > 0 && <p>{facts.paragraphs.join(" ")}</p>}
              <DialogButton ref={more} className="rt-more" onClick={() => {
                setMounted(true);
                setOpen(true);
              }}>More info...</DialogButton>
            </div>
          )}
        </div>
        {mounted && <GameInfo system={system} game={game} facts={facts} firstRef={first} onBack={() => setOpen(false)} />}
      </div>
    </Focusable>
  );
}

export const KINDS: Kind[] = ["portrait", "landscape", "hero", "logo", "icon"];

// Opens the choice of the game's images over its page, one tab per kind. The dialog stays open
// after a pick, so that several kinds change in one visit.
export function customize(system: string, path: string, first: Kind = "portrait") {
  const modal = showModal(
    <ModalRoot bAllowFullSize onCancel={() => modal.Close()} closeModal={() => modal.Close()}>
      <style>{CSS}</style>
      <div className="rt-modal"><ArtTabs system={system} path={path} first={first} /></div>
    </ModalRoot>,
  );
}

function ArtTabs({ system, path, first }: { system: string; path: string; first: Kind }) {
  const [kind, setKind] = useState<Kind>(first);
  return (
    <div className="rt-modal-tabs">
      <Tabs activeTab={kind} onShowTab={(k: string) => setKind(k as Kind)} tabs={KINDS.map((k) => ({
        id: k, title: KIND_LABEL[k], content: <Tab><Candidates system={system} path={path} kind={k} /></Tab>,
      }))} />
    </div>
  );
}

// Candidates by game and kind, kept while Steam runs.
const offers = new Map<string, Promise<{ current: string | null; items: Candidate[] }>>();

function CandidateCard({ kind, item, current, onPick }:
  { kind: Kind; item: Candidate; current: boolean; onPick: () => void }) {
  const [broken, setBroken] = useState(false);
  if (broken) return null;
  const size = item.size ? ` ${item.size[0]}×${item.size[1]}` : "";
  return (
    <Focusable className={`rt-card${kind === "logo" ? " rt-logo" : ""}`} onActivate={onPick}
      onOKActionDescription="Use this image">
      <div className="rt-media">
        <Frame id={item.thumb ?? item.id} ratio={RATIO[kind]} plain={kind === "logo"} onError={() => setBroken(true)} />
        {current && <span className="rt-badge">Current</span>}
      </div>
      <div className="rt-label">{item.source} {item.label.toLowerCase()}{size}</div>
    </Focusable>
  );
}

function Candidates({ system, path, kind }: { system: string; path: string; kind: Kind }) {
  const [offer, setOffer] = useState<{ current: string | null; items: Candidate[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const key = `${path}\n${kind}`;
    if (!offers.has(key)) offers.set(key, getCandidates(system, path, kind));
    setOffer(null);
    offers.get(key)!.then(setOffer, (e) => {
      offers.delete(key);
      setError(String(e));
    });
  }, [system, path, kind]);
  if (error) return <div className="rt-empty">{error}</div>;
  if (!offer) return <SteamSpinner />;
  if (offer.items.length === 0) return <div className="rt-empty">No image found.</div>;
  const pick = (item: Candidate) => {
    const previous = offer.current;
    const next = { ...offer, current: item.id };
    offers.set(`${path}\n${kind}`, Promise.resolve(next));
    setOffer(next);
    // The game page looks the image up again once Steam has it.
    forgetPicture(path, kind);
    pickImage(system, path, kind, item.id).then((ok) => {
      if (ok) return;
      const back = { ...next, current: previous };
      offers.set(`${path}\n${kind}`, Promise.resolve(back));
      setOffer(back);
    });
  };
  return (
    <Focusable className={`rt-grid rt-art-${kind}`} flow-children="grid">
      {offer.items.map((item) => (
        <CandidateCard key={item.id} kind={kind} item={item} current={item.id === offer.current}
          onPick={() => pick(item)} />
      ))}
    </Focusable>
  );
}

export function GamePage() {
  const s = useStore();
  const selected = s.selected;
  const game = selected && findGame(selected.system, selected.path);
  useEffect(() => {
    if (selected && !game) loadGames(selected.system);
  }, [selected?.path]);
  // Each game gets its own view: L1 and R1 start the next one at the top, with its own images.
  return <Page bare>{selected && game ? <GameView key={game.path} system={selected.system} game={game} /> : <SteamSpinner />}</Page>;
}
