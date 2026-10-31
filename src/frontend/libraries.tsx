import { DialogButton, Focusable, Navigation, SteamSpinner } from "@decky/ui";
import { ReactNode, useEffect, useState } from "react";
import { Page, formatSize, openGames } from "./page";
import { SAMPLE_PLACES, Scenario, sampleLibraries } from "./samples";
import { refresh } from "./store";
import {
  DriveKind, Library, NewLibrary, combineLibraries, createLibrary, findLibraries, getNewLibraries, pickLibrary,
} from "./tiles";

export const LIBRARIES_ROUTE = "/rom-library/libraries";

// The panel shows 10 systems at most. With more, the last cell counts the others.
const SHOWN = 10;
// The search stays on screen 1 s at least. A faster scan would only flash it.
const SEARCH_MS = 1000;

// Draws a line icon on a 24px grid in the text's colour.
function Glyph({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
      strokeLinejoin="round">
      {children}
    </svg>
  );
}

const DRIVE: Record<DriveKind, ReactNode> = {
  // A memory chip.
  internal: (
    <>
      <rect x="5" y="5" width="14" height="14" rx="2" />
      <rect x="9" y="9" width="6" height="6" rx="1" />
      <path d="M9 2v3M12 2v3M15 2v3M9 19v3M12 19v3M15 19v3M2 9h3M2 12h3M2 15h3M19 9h3M19 12h3M19 15h3" />
    </>
  ),
  sd: (
    <>
      <path d="M8 2h7l4 4v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a3 3 0 0 1 3-3z" />
      <path d="M9 5v3M12 5v3M15 6v2" />
    </>
  ),
  usb: (
    <>
      <rect x="6" y="9" width="12" height="13" rx="2" />
      <path d="M8.5 9V2h7v7" />
      <path d="M11 5h0M13 5h0" />
    </>
  ),
};

// Draws a lens over the plugin's four tiles. The panel shows it while the scan runs.
function Lens() {
  return (
    <svg className="rt-lens" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round">
      <circle cx="10" cy="10" r="7" strokeWidth="1" />
      <path d="M15.2 15.2 21.5 21.5" strokeWidth="2.5" />
      <g fill="currentColor" stroke="none">
        <rect x="6.6" y="6.6" width="3" height="3" rx="0.5" />
        <rect x="10.4" y="6.6" width="3" height="3" rx="0.5" />
        <rect x="6.6" y="10.4" width="3" height="3" rx="0.5" />
        <rect x="10.4" y="10.4" width="3" height="3" rx="0.5" />
      </g>
    </svg>
  );
}

const count = (n: number) => n.toLocaleString("en-US");

// Open Library sets it until the user chooses a library. The page then uses a single folder without a
// question.
let firstUse = false;

export function openLibraries(first = false) {
  firstUse = first;
  Navigation.Navigate(LIBRARIES_ROUTE);
  Navigation.CloseSideMenus();
}

// Opens the games once the backend reads the chosen folders.
function done(change: Promise<void>) {
  change.then(refresh).then(openGames, () => undefined);
}

// Returns the name of a library's drive. Two libraries on one drive add their top folder, such as
// Internal Storage · Downloads.
function label(lib: Library, libs: Library[]): string {
  const shared = libs.filter((l) => l.drive.name === lib.drive.name).length > 1;
  return shared ? `${lib.drive.name} · ${lib.where.split("/")[1]}` : lib.drive.name;
}

type Role = "main" | "included";
const FS_NAME: Record<string, string> = { exfat: "exFAT", vfat: "FAT32", ntfs: "NTFS", ntfs3: "NTFS" };

// Returns the library with the most games among those that hold links.
function recommended(libs: Library[]): Library | null {
  return libs.filter((l) => l.links).sort((a, b) => b.games - a.games)[0] ?? null;
}

// A library barely overlaps the main one when 5% of its games or fewer belong to systems the main
// library also has. ES-DE leaves those games out of a combined library.
function fits(lib: Library, main: Library): boolean {
  const theirs = new Map(main.systems.map((s) => [s.id, s.games]));
  const shared = lib.systems.reduce((n, s) => n + Math.min(s.games, theirs.get(s.id) ?? 0), 0);
  return shared * 20 <= lib.games;
}

// Returns the remark under a library's systems, or null. 'chosen' is true once the user set a main
// library.
function remark(lib: Library, libs: Library[], main: Library | null, chosen: boolean, role?: Role): ReactNode {
  if (!main) {
    return lib.links || libs.length < 2 ? null : (
      <><strong>Note:</strong> this location is on {FS_NAME[lib.fs] ?? lib.fs} and can't be used to include other
        libraries.</>
    );
  }
  if (lib.path === main.path) {
    return chosen || libs.length < 2 ? null
      : <><strong>Recommended:</strong> make this the main library and include the others in it.</>;
  }
  return !role && fits(lib, main)
    ? <><strong>Tip:</strong> include this library in the main one to see all your games together.</> : null;
}

// Shows a library in the list: its drive, then its number of games. Once the user sets a main library,
// the rows show their role alone: a badge on the main one, a word on the included ones.
function LibraryRow({ lib, name, role, combining, first, actions }:
  { lib: Library; name: string; role?: Role; combining: boolean; first: boolean; actions: object }) {
  let end: ReactNode = count(lib.games);
  if (role === "main") end = <span className="rt-setbadge">Main</span>;
  else if (role === "included") end = "included";
  else if (combining) end = null;
  return (
    <Focusable className="rt-lib" focusClassName="rt-focus" preferredFocus={first} {...actions}>
      <span className="rt-lib-name">{name}</span>
      {end != null && <span className="rt-lib-count">{end}</span>}
    </Focusable>
  );
}

// Shows the drive's icon, its name and the library's path at the top of the panel.
function Head({ drive, path }: { drive: Library["drive"]; path: string }) {
  return (
    <>
      <div className="rt-detail-drive"><Glyph>{DRIVE[drive.kind]}</Glyph></div>
      <div className="rt-detail-name">{drive.name}</div>
      <div className="rt-detail-path">{path}</div>
    </>
  );
}

// Lists the systems in two columns, with their games when the library has some.
function Systems({ systems }: { systems: { id: string; name: string; games?: number }[] }) {
  const shown = systems.length > SHOWN ? systems.slice(0, SHOWN - 1) : systems;
  return (
    <div className="rt-detail-systems">
      {shown.map((s) => (
        <div className="rt-system" key={s.id}>
          <span className="rt-system-name">{s.name}</span>
          {s.games != null && <span className="rt-system-count">{count(s.games)}</span>}
        </div>
      ))}
      {shown.length < systems.length && (
        <div className="rt-system rt-system-more">{systems.length - shown.length} more</div>
      )}
    </div>
  );
}

// Shows the focused library right of the drive's icon: its drive, its path, its numbers and its
// systems. The path tells apart two libraries on one drive.
function Detail({ lib, note }: { lib: Library; note: ReactNode }) {
  const systems = [...lib.systems].sort((a, b) => b.games - a.games);
  return (
    <div className="rt-detail">
      <Head drive={lib.drive} path={lib.path} />
      <dl className="rt-stats rt-detail-stats">
        <div className="rt-stat"><dt>Games</dt><dd>{count(lib.games)}</dd></div>
        <div className="rt-stat"><dt>Systems</dt><dd>{systems.length}</dd></div>
        {lib.usedBy.length > 0 && <div className="rt-stat"><dt>Used by</dt><dd>{lib.usedBy.join(", ")}</dd></div>}
      </dl>
      <div className="rt-detail-rule" />
      <Systems systems={systems} />
      {note && <p className="rt-detail-note">{note}</p>}
    </div>
  );
}

// Shows the library Create a New Library makes: its drive, its path, the drive's free space and a
// folder per system.
function NewDetail({ lib }: { lib: NewLibrary }) {
  return (
    <div className="rt-detail">
      <Head drive={lib.drive} path={lib.path} />
      <dl className="rt-stats rt-detail-stats">
        <div className="rt-stat"><dt>Folders</dt><dd>{lib.systems.length}</dd></div>
        <div className="rt-stat"><dt>Free space</dt><dd>{formatSize(lib.free)}</dd></div>
      </dl>
      <div className="rt-detail-rule" />
      <Systems systems={lib.systems} />
    </div>
  );
}

// Shows what Use All makes: the main library, or a new one when no library holds links. The numbers
// and the systems add up every library.
function AllDetail({ libs, main, place }: { libs: Library[]; main: Library | null; place: NewLibrary | null }) {
  const games = new Map<string, { id: string; name: string; games: number }>();
  for (const l of libs) {
    for (const s of l.systems) {
      const g = games.get(s.id);
      games.set(s.id, { ...s, games: (g?.games ?? 0) + s.games });
    }
  }
  const systems = [...games.values()].sort((a, b) => b.games - a.games);
  const head = main ?? place;
  return (
    <div className="rt-detail">
      {head && <Head drive={head.drive} path={head.path} />}
      <dl className="rt-stats rt-detail-stats">
        <div className="rt-stat"><dt>Games</dt><dd>{count(libs.reduce((n, l) => n + l.games, 0))}</dd></div>
        <div className="rt-stat"><dt>Systems</dt><dd>{systems.length}</dd></div>
        <div className="rt-stat"><dt>Locations</dt><dd>{libs.length}</dd></div>
      </dl>
      <div className="rt-detail-rule" />
      <Systems systems={systems} />
    </div>
  );
}

// A scenario's sample libraries replace the scan, to review each screen: "searching", "none", "one",
// "several", "exfat" or "organizer". null runs the scan.
const SCENARIO: Scenario | null = null;

// Lists the ROM folders the scan found, the largest first, with their drive and games. The panel
// shows the focused one in full. Without a folder, the page offers a new library. One folder becomes
// the main library. Use All takes several folders. Organize… opens the organizer: X sets the main
// library and the included ones.
export function LibrariesPage() {
  const [libs, setLibs] = useState<Library[] | null>(null);
  const [shown, setShown] = useState<string | null>(null);
  const [places, setPlaces] = useState<NewLibrary[]>([]);
  const [place, setPlace] = useState(0);
  const [onNew, setOnNew] = useState(false);
  const [onAll, setOnAll] = useState(false);
  const [onOrganize, setOnOrganize] = useState(false);
  const [organize, setOrganize] = useState(SCENARIO === "organizer");
  const [roles, setRoles] = useState<Record<string, Role>>({});
  // A hot reload runs the scan again: the page starts over, in the organizer for that scenario.
  useEffect(() => {
    setLibs(null);
    setRoles({});
    setShown(null);
    setOrganize(SCENARIO === "organizer");
    setOnAll(false);
    setOnOrganize(false);
    setOnNew(false);
    if (SCENARIO === "searching") return;
    const delay = new Promise((resolve) => setTimeout(resolve, SEARCH_MS));
    const scan = SCENARIO ? Promise.resolve(sampleLibraries(SCENARIO)) : findLibraries();
    // The new library comes with the scan: Create a New Library takes the focus when it shows.
    const where = SCENARIO ? Promise.resolve(SAMPLE_PLACES) : getNewLibraries().catch(() => []);
    Promise.all([scan, where, delay]).then(([found, where]) => {
      const first = firstUse;
      firstUse = false;
      if (first && !SCENARIO && found.length === 1) return done(pickLibrary(found[0].path));
      setPlaces(where);
      setPlace(0);
      const sorted = [...found].sort((a, b) => b.games - a.games);
      setLibs(sorted);
      // setLibs([]);
    }, () => delay.then(() => setLibs([])));
  }, []);
  const detail = libs?.find((l) => l.path === shown) ?? libs?.[0];
  const newLib = places[place] ?? null;
  // The main library is the one the user set, else the recommended one.
  const chosen = Object.keys(roles).find((p) => roles[p] === "main");
  const main = libs?.find((l) => l.path === chosen) ?? (libs && recommended(libs)) ?? null;
  const included = Object.keys(roles).filter((p) => roles[p] === "included");
  const combining = Object.keys(roles).length > 0;

  // X sets a library as the main one, includes it in the main one, or takes its role back. Taking the
  // main library's role back clears every role.
  function act(lib: Library): { label: string; run: () => void } | null {
    const role = roles[lib.path];
    if (role === "main") return { label: "Remove", run: () => setRoles({}) };
    if (role === "included") {
      return { label: "Remove", run: () => setRoles(Object.fromEntries(Object.entries(roles).filter(([p]) => p !== lib.path))) };
    }
    if (!chosen && lib.links) return { label: "Set as Main", run: () => setRoles({ ...roles, [lib.path]: "main" }) };
    if (!main || lib.path === main.path) return null;
    return { label: "Include", run: () => setRoles({ ...roles, [main.path]: "main", [lib.path]: "included" }) };
  }

  function use(lib: Library) {
    done(combining && main ? combineLibraries(main.path, included) : pickLibrary(lib.path));
  }

  // Use All includes every library in the main one, or in a new one when none holds links.
  function useAll() {
    if (!libs) return;
    const others = libs.filter((l) => l !== main).map((l) => l.path);
    if (main) done(combineLibraries(main.path, others));
    else if (newLib) done(createLibrary(newLib.path, others));
  }

  const changeDrive = {
    onSecondaryButton: places.length > 1 ? () => setPlace((place + 1) % places.length) : undefined,
    onSecondaryActionDescription: places.length > 1 ? "Change Drive" : undefined,
  };
  const several = !!libs && libs.length > 1;
  let side: ReactNode;
  if (!libs) {
    side = <><h2>Looking for ROMs</h2><SteamSpinner /></>;
  } else if (libs.length === 0) {
    side = (
      <>
        <h2>No ROMs found</h2>
        <p>We looked into the most common locations.</p>
        <Focusable className="rt-libs-list" flow-children="column">
          <DialogButton className="rt-new" disabled={!newLib}
	    preferredFocus={true}
            onGamepadFocus={() => setOnNew(true)} onGamepadBlur={() => setOnNew(false)}
            onClick={() => newLib && done(createLibrary(newLib.path, []))} {...changeDrive}>
            Create a New Library
          </DialogButton>
          {newLib && <p className="rt-libs-note">The new library will feature per-console folders to hold your ROMS.</p>}
        </Focusable>
      </>
    );
  } else if (several && !organize) {
    side = (
      <>
        <h2>Found {libs.length} locations</h2>
        <p>{onOrganize ? "Set main and combine libraries." : "We'll use all of them."}</p>
        <Focusable className="rt-libs-list" flow-children="column">
          {libs.map((l) => (
            <LibraryRow key={l.path} lib={l} name={label(l, libs)} combining={false} first={false} actions={{
              onGamepadFocus: () => setShown(l.path),
              onActivate: useAll,
              onOKActionDescription: "Use All",
            }} />
          ))}
          <Focusable className="rt-libs-actions" flow-children="row">
            <DialogButton preferredFocus onGamepadFocus={() => setOnAll(true)} onGamepadBlur={() => setOnAll(false)}
              onClick={useAll}>
              Use All
            </DialogButton>
            <DialogButton onGamepadFocus={() => setOnOrganize(true)} onGamepadBlur={() => setOnOrganize(false)}
              onClick={() => setOrganize(true)}>
              Organize…
            </DialogButton>
          </Focusable>
        </Focusable>
      </>
    );
  } else {
    // Libraries on exFAT alone cannot be combined: a new main library on the internal storage can
    // include them.
    const noMain = several && !main;
    const games = libs[0].games;
    let title = `Found ${count(games)} ${games === 1 ? "ROM" : "ROMs"}`;
    let lede = "We found games in this location.";
    if (several) {
      title = "Organize Libraries";
      lede = "Set the main library and include the others.";
    }
    if (noMain) {
      title = `Found ${libs.length} locations`;
      lede = "Select one of these libraries.";
    }
    side = (
      <>
        <h2>{title}</h2>
        <p>{lede}</p>
        <Focusable className="rt-libs-list" flow-children="column"
          onCancel={several ? () => setOrganize(false) : undefined}>
          {libs.map((l, i) => {
            const x = several ? act(l) : null;
            return (
              <LibraryRow key={l.path} lib={l} name={label(l, libs)} role={roles[l.path]} combining={combining}
                first={i === 0} actions={{
                onGamepadFocus: () => setShown(l.path),
                onActivate: () => use(l),
                onOKActionDescription: combining ? "Combine Libraries" : "Use This Library",
                onSecondaryButton: x?.run,
                onSecondaryActionDescription: x?.label,
              }} />
            );
          })}
          {noMain && (
            <>
              <p className="rt-libs-note rt-libs-or">Or create a main library capable of including these.</p>
              <DialogButton className="rt-new" disabled={!newLib}
                onGamepadFocus={() => setOnNew(true)} onGamepadBlur={() => setOnNew(false)}
                onClick={() => newLib && done(createLibrary(newLib.path, libs.map((l) => l.path)))}
                {...changeDrive}>
                Create a Main Library
              </DialogButton>
            </>
          )}
        </Focusable>
      </>
    );
  }
  let panel: ReactNode = <div className="rt-detail rt-searching"><Lens /></div>;
  if (onNew && newLib) panel = <NewDetail lib={newLib} />;
  else if (onAll && libs) panel = <AllDetail libs={libs} main={main} place={newLib} />;
  else if (libs && detail) {
    const note = several && organize ? remark(detail, libs, main, !!chosen, roles[detail.path]) : null;
    panel = <Detail lib={detail} note={note} />;
  }
  return (
    <Page searchBar={false}>
      <Focusable className="rt-libs" flow-children="row">
        <div className="rt-libs-side">{side}</div>
        {panel}
      </Focusable>
    </Page>
  );
}
