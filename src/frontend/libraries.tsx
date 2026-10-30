import { DialogButton, Focusable, SteamSpinner } from "@decky/ui";
import { ReactNode, useEffect, useState } from "react";
import { Page, formatSize, openGames } from "./page";
import {
  DriveKind, Library, NewLibrary, combineLibraries, createLibrary, findLibraries, getNewLibraries, pickLibrary,
} from "./tiles";

export const LIBRARIES_ROUTE = "/rom-library/libraries";

// The systems the detail lists. A last cell counts the others.
const SHOWN = 10;
// The search stays on screen 1 s at least. A faster scan would only flash it.
const SEARCH_MS = 1000;

// A line icon on a 24px grid, in the text's colour.
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

// A lens over the plugin's four tiles, shown while the scan runs.
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

function SearchIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="6.5" cy="6.5" r="5" /><path d="M10.5 10.5 15 15" />
    </svg>
  );
}

const count = (n: number) => n.toLocaleString("en-US");

// The name of a library's drive. Two libraries on one drive add their top folder, such as
// Internal Storage · Downloads.
function label(lib: Library, libs: Library[]): string {
  const shared = libs.filter((l) => l.drive.name === lib.drive.name).length > 1;
  return shared ? `${lib.drive.name} · ${lib.where.split("/")[1]}` : lib.drive.name;
}

type Role = "main" | "included";
const FS_NAME: Record<string, string> = { exfat: "exFAT", vfat: "FAT32", ntfs: "NTFS", ntfs3: "NTFS" };

// The library with the most games among those that can hold links.
function recommended(libs: Library[]): Library | null {
  return libs.filter((l) => l.links).sort((a, b) => b.games - a.games)[0] ?? null;
}

// A library barely overlaps the main one when 5% of its games or fewer belong to systems the main
// library also has. A combined library leaves those games out.
function fits(lib: Library, main: Library): boolean {
  const theirs = new Map(main.systems.map((s) => [s.id, s.games]));
  const shared = lib.systems.reduce((n, s) => n + Math.min(s.games, theirs.get(s.id) ?? 0), 0);
  return shared * 20 <= lib.games;
}

// The remark under a library's systems, when one applies. 'chosen' tells that the user set a main
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

// A library in the list: its drive, then its number of games. Once a main library is set, the rows
// show their role alone: a badge on the main one, a word on the included ones.
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

// The drive's icon, its name and the library's path, at the top of the panel.
function Head({ drive, path }: { drive: Library["drive"]; path: string }) {
  return (
    <>
      <div className="rt-detail-drive"><Glyph>{DRIVE[drive.kind]}</Glyph></div>
      <div className="rt-detail-name">{drive.name}</div>
      <div className="rt-detail-path">{path}</div>
    </>
  );
}

// The systems in two columns, with their games when the library has some.
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

// The focused library: its drive, its full path, the tool that set it and its systems, in one
// column right of the drive's icon. The path tells apart two libraries on one drive.
function Detail({ lib, note }: { lib: Library; note: ReactNode }) {
  const systems = [...lib.systems].sort((a, b) => b.games - a.games);
  return (
    <div className="rt-detail">
      <Head drive={lib.drive} path={lib.path} />
      <dl className="rt-stats rt-detail-stats">
        <div className="rt-stat"><dt>Games</dt><dd>{count(lib.games)}</dd></div>
        <div className="rt-stat"><dt>Systems</dt><dd>{systems.length}</dd></div>
        {lib.source && <div className="rt-stat"><dt>Set by</dt><dd>{lib.source}</dd></div>}
      </dl>
      <div className="rt-detail-rule" />
      <Systems systems={systems} />
      {note && <p className="rt-detail-note">{note}</p>}
    </div>
  );
}

// The library Create a New Library would make: its drive, its path, the drive's free space and a
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

// The ROM folders the scan found, the largest first, for the user to pick one. The list shows each
// folder's drive and games. The panel shows the focused one in full. Without a folder, the page
// offers the deep search and a new library.
export function LibrariesPage() {
  const [libs, setLibs] = useState<Library[] | null>(null);
  const [deep, setDeep] = useState(false);
  const [shown, setShown] = useState<string | null>(null);
  const [places, setPlaces] = useState<NewLibrary[]>([]);
  const [place, setPlace] = useState(0);
  const [onNew, setOnNew] = useState(false);
  const [roles, setRoles] = useState<Record<string, Role>>({});
  useEffect(() => {
    setLibs(null);
    setRoles({});
    const delay = new Promise((resolve) => setTimeout(resolve, SEARCH_MS));
    // The new library comes with the scan: Create a New Library takes the focus when it shows.
    Promise.all([findLibraries(deep), getNewLibraries().catch(() => []), delay]).then(([found, where]) => {
      setPlaces(where);
      setPlace(0);
      const sorted = [...found].sort((a, b) => b.games - a.games);
      setLibs(sorted);
      // setLibs([]);
    }, () => delay.then(() => setLibs([])));
  }, [deep]);
  const detail = libs?.find((l) => l.path === shown) ?? libs?.[0];
  const newLib = places[place] ?? null;
  // The main library: the one the user set, else the recommended one.
  const chosen = Object.keys(roles).find((p) => roles[p] === "main");
  const main = libs?.find((l) => l.path === chosen) ?? (libs && recommended(libs));
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
    const done = combining && main ? combineLibraries(main.path, included) : pickLibrary(lib.path);
    done.then(openGames, () => undefined);
  }

  const search = !deep && libs && (
    <>
      <p className="rt-libs-note rt-libs-more">We could search further into your system.</p>
      <DialogButton className="rt-deep" onClick={() => setDeep(true)}>
        <SearchIcon />Search More Folders
      </DialogButton>
    </>
  );
  const changeDrive = {
    onSecondaryButton: places.length > 1 ? () => setPlace((place + 1) % places.length) : undefined,
    onSecondaryActionDescription: places.length > 1 ? "Change Drive" : undefined,
  };
  let side: ReactNode;
  if (!libs) {
    side = <><h2>Looking for ROMs</h2><SteamSpinner /></>;
  } else if (libs.length === 0) {
    side = (
      <>
        <h2>No ROMs found</h2>
        <p>
          {deep ? "We looked into every folder."
            : "We looked into the most common locations."}
        </p>
        <Focusable className="rt-libs-list" flow-children="column">
          {search}
          {search && <div className="rt-libs-rule" />}
          <DialogButton className="rt-new" disabled={!newLib}
	    preferredFocus={true}
            onGamepadFocus={() => setOnNew(true)} onGamepadBlur={() => setOnNew(false)}
            onClick={() => newLib && createLibrary(newLib.path, []).then(openGames, () => undefined)} {...changeDrive}>
            Create a New Library
          </DialogButton>
          {newLib && <p className="rt-libs-note">The new library will feature per-console folders to hold your ROMS.</p>}
        </Focusable>
      </>
    );
  } else {
    const games = libs[0].games;
    // Libraries on exFAT alone cannot be combined: a new main library on the internal storage can
    // include them.
    const noMain = libs.length > 1 && !main;
    let title = libs.length > 1 ? `Found ${libs.length} places` : `Found ${count(games)} ${games === 1 ? "ROM" : "ROMs"}`;
    let lede = `${libs.length > 1 ? "Pick" : "Config"} the library to show in Steam.`;
    if (noMain) {
      title = `Found ${libs.length} locations`;
      lede = "Select one of these libraries.";
    }
    side = (
      <>
        <h2>{title}</h2>
        <p>{lede}</p>
        <Focusable className="rt-libs-list" flow-children="column">
          {libs.map((l, i) => {
            const x = act(l);
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
                onClick={() => newLib && createLibrary(newLib.path, libs.map((l) => l.path)).then(openGames, () => undefined)}
                {...changeDrive}>
                Create a Main Library
              </DialogButton>
            </>
          )}
          {search}
        </Focusable>
      </>
    );
  }
  let panel: ReactNode = <div className="rt-detail rt-searching"><Lens /></div>;
  if (onNew && newLib) panel = <NewDetail lib={newLib} />;
  else if (libs && detail) panel = <Detail lib={detail} note={remark(detail, libs, main ?? null, !!chosen, roles[detail.path])} />;
  return (
    <Page searchBar={false}>
      <Focusable className="rt-libs" flow-children="row">
        <div className="rt-libs-side">{side}</div>
        {panel}
      </Focusable>
    </Page>
  );
}
