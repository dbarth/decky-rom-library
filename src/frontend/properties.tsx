import {
  DialogButton, DropdownItem, Field, SidebarNavigation, SteamSpinner, ToggleField, gamepadDialogClasses,
} from "@decky/ui";
import { ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useEmulatorSettings, useRomFiles } from "./hooks";
import { KINDS, Page, Spinner, confirmUninstall, customize, formatSize } from "./page";
import { KIND_LABEL, findGame, loadGames, toggleTile, useStore } from "./store";
import { PANEL_CSS } from "./styles";
import { EmulatorSettings, Game } from "./tiles";

// Matches no option: Steam's dropdown then shows strDefaultLabel on its button.
const NO_OPTION = {};

// A setting of the game in its emulator. The button shows the value alone. The list's first option,
// Default, removes the game's value and names the emulator's own. A value the game sets puts the
// Custom badge after the label.
function SettingDropdown({ label, options, byDefault, value, disabled, onChange }: {
  label: string; options: [string, string][]; byDefault: string; value: string | null;
  disabled?: boolean; onChange: (value: string | null) => void;
}) {
  const text = (v: string) => options.find(([data]) => data === v)?.[1] ?? v;
  const rgOptions = [
    { data: null, label: `Default (${text(byDefault)})` },
    ...options.map(([data, t]) => ({ data, label: t })),
  ];
  const badged = <span className="rt-setlabel">{label}<span className="rt-setbadge">Custom</span></span>;
  return (
    <DropdownItem label={value == null ? label : badged} rgOptions={rgOptions}
      selectedOption={value ?? NO_OPTION} strDefaultLabel={text(byDefault)} disabled={disabled}
      onChange={(o) => onChange(o.data)} />
  );
}

type Emulator = [EmulatorSettings | null | undefined, (key: string, value: string | null) => void];

// One of the game's settings that the plugin writes in its emulator.
function Setting({ label, name, options, emulator: [settings, set], disabled }: {
  label: string; name: string; options: [string, string][]; emulator: Emulator;
  disabled?: boolean;
}) {
  if (!settings) return null;
  return (
    <SettingDropdown label={label} options={options} byDefault={settings.globals[name]}
      value={settings.values[name]} disabled={disabled} onChange={(v) => set(name, v)} />
  );
}

// Dolphin's values, as its INIs write them, and their names in Dolphin's own settings.
const DOLPHIN: Record<string, [string, string][]> = {
  aspect: [["0", "Auto"], ["1", "Force 16:9"], ["2", "Force 4:3"]],
  resolution: [["1", "Native (640×528)"], ["2", "2x (720p)"], ["3", "3x (1080p)"]],
  backend: [["Vulkan", "Vulkan"], ["OGL", "OpenGL"]],
  wiimote: [["Wii Remote and Nunchuk", "Wii Remote and Nunchuk"], ["Sideways Wii Remote", "Sideways Wii Remote"],
    ["Classic Controller", "Classic Controller"]],
};

// Eden's values, as its INI writes them, and their names in Eden's own settings. A language or a
// region is its index in Eden's list.
const EDEN: Record<string, [string, string][]> = {
  language: [["1", "American English"], ["17", "Brazilian Portuguese"], ["12", "British English"],
    ["13", "Canadian French"], ["6", "Chinese"], ["8", "Dutch"], ["2", "French"], ["3", "German"], ["4", "Italian"],
    ["0", "Japanese"], ["7", "Korean"], ["14", "Latin American Spanish"], ["18", "Polish"], ["9", "Portuguese"],
    ["10", "Russian"], ["15", "Simplified Chinese"], ["5", "Spanish"], ["11", "Taiwanese"], ["19", "Thai"],
    ["16", "Traditional Chinese"]],
  region: [["0", "Japan"], ["1", "USA"], ["2", "Europe"], ["3", "Australia"], ["4", "China"], ["5", "Korea"],
    ["6", "Taiwan"]],
  docked: [["1", "Docked"], ["0", "Handheld"]],
  resolution: [["1", "0.5x (360p/540p)"], ["2", "0.75x (540p/810p)"], ["3", "1x (720p/1080p)"],
    ["4", "1.25x (900p/1350p)"], ["5", "1.5x (1080p/1620p)"], ["6", "2x (1440p/2160p)"], ["7", "3x (2160p/3240p)"],
    ["8", "4x (2880p/4320p)"]],
  accuracy: [["0", "Fast"], ["1", "Accurate"]],
  anisotropy: [["0", "Automatic"], ["1", "Default"], ["2", "2x"], ["3", "4x"], ["4", "8x"], ["5", "16x"]],
  filter: [["0", "Nearest"], ["1", "Bilinear"], ["2", "Bicubic"], ["8", "Zero-Tangent"], ["9", "B-Spline"],
    ["10", "Mitchell"], ["11", "Spline-1"], ["3", "Gaussian"], ["4", "Lanczos"], ["5", "ScaleForce"], ["6", "FSR"],
    ["7", "Area"], ["12", "MMPX"], ["13", "SGSR"], ["14", "SGSR EdgeDir"]],
};

// RetroArch's run-ahead, in frames.
const RUN_AHEAD: [string, string][] = [["0", "Off"], ["1", "1 frame"], ["2", "2 frames"]];

const ON_OFF: [string, string][] = [["true", "On"], ["false", "Off"]];

// The gyroscope of Eden and Dolphin, read from the DSU server. The row stays, disabled, while the
// server does not run.
function Gyroscope({ emulator }: { emulator: Emulator }) {
  return (
    <Setting label="Gyroscope" name="gyro" options={ON_OFF} emulator={emulator}
      disabled={!emulator[0]?.dsu} />
  );
}

// Where each Wii Remote layout puts the remote's buttons on the gamepad.
const WIIMOTE_HELP: Record<string, string> = {
  "Wii Remote and Nunchuk": "A on the bottom button, B on the right one or R2, 1 on the left one, 2 on the top one, "
    + "shake on R1. The left stick, L1 and L2 are the Nunchuk's stick, C and Z. The right stick points.",
  "Sideways Wii Remote": "2 on the bottom button, 1 on the left one, A on the right one, shake on the top one or "
    + "R1. The D-pad and the left stick move, the right stick tilts.",
  "Classic Controller": "a, b, x and y sit as on a Nintendo pad: a on the right, b at the bottom.",
};


// A GameCube disc has no Controller page.
function dolphinPages(emulator: Emulator): PropertyPage[] {
  const [settings] = emulator;
  const layout = settings ? settings.values.wiimote ?? settings.globals.wiimote : "";
  return [{
    title: "Display", identifier: "display", content: (
      <>
        <Setting label="Aspect ratio" name="aspect" options={DOLPHIN.aspect} emulator={emulator} />
        <Setting label="Resolution" name="resolution" options={DOLPHIN.resolution} emulator={emulator} />
        <Setting label="Renderer" name="backend" options={DOLPHIN.backend} emulator={emulator} />
      </>
    ),
  }, ...settings?.console === "gc" ? [] : [{
    title: "Controller", identifier: "controller", content: (
      <>
        <Setting label="Wii Remote" name="wiimote" options={DOLPHIN.wiimote} emulator={emulator} />
        {WIIMOTE_HELP[layout] && <p className="rt-prop-note">{WIIMOTE_HELP[layout]}</p>}
        <Gyroscope emulator={emulator} />
      </>
    ),
  }]];
}

function edenPages(emulator: Emulator): SystemPages {
  return {
    language: (
      <>
        <Setting label="Language" name="language" options={EDEN.language} emulator={emulator} />
        <Setting label="Region" name="region" options={EDEN.region} emulator={emulator} />
      </>
    ),
    pages: [{
      title: "Display", identifier: "display", content: (
        <>
          <Setting label="Console mode" name="docked" options={EDEN.docked} emulator={emulator} />
          <Setting label="Resolution" name="resolution" options={EDEN.resolution} emulator={emulator} />
          <Setting label="Scaling filter" name="filter" options={EDEN.filter} emulator={emulator} />
          <div className="rt-prop-heading">Advanced settings</div>
          <Setting label="GPU accuracy" name="accuracy" options={EDEN.accuracy} emulator={emulator} />
          <Setting label="Asynchronous GPU" name="async_gpu" options={ON_OFF} emulator={emulator} />
          <Setting label="Asynchronous shaders" name="async_shaders" options={ON_OFF} emulator={emulator} />
          <Setting label="Reactive flushing" name="reactive_flushing" options={ON_OFF} emulator={emulator} />
          <Setting label="Anisotropic filtering" name="anisotropy" options={EDEN.anisotropy} emulator={emulator} />
        </>
      ),
    }, {
      title: "Controller", identifier: "controller", content: (
        <>
          <SwapButtons emulator={emulator} />
          <Gyroscope emulator={emulator} />
        </>
      ),
    }],
  };
}

// Eden has no global setting to swap A and B: the game swaps them in its own copy of the buttons.
function SwapButtons({ emulator: [settings, set] }: { emulator: Emulator }) {
  if (!settings) return null;
  return (
    <ToggleField label="Swap A and B" checked={settings.values.swap === "true"}
      onChange={(on) => set("swap", on ? "true" : null)} />
  );
}

// A game without a bezel has no Display page.
function retroarchPages(emulator: Emulator): PropertyPage[] {
  return [...emulator[0]?.overlay ? [{
    title: "Display", identifier: "display", content: (
      <Setting label="Show bezel" name="bezel" options={ON_OFF} emulator={emulator} />
    ),
  }] : [], {
    title: "RetroArch", identifier: "emulator", content: (
      <>
        <Setting label="Run-ahead" name="run_ahead" options={RUN_AHEAD} emulator={emulator} />
        <Setting label="Rewind" name="rewind" options={ON_OFF} emulator={emulator} />
      </>
    ),
  }];
}

interface PropertyPage {
  title: string;
  identifier: string;
  content: ReactNode;
}

// What a system adds: the rows of General's Language section, and the pages between General and
// Images.
interface SystemPages {
  language?: ReactNode;
  pages: PropertyPage[];
}

// The pages of the emulators whose settings the plugin writes: Dolphin, Eden and RetroArch.
function systemPages([settings, set]: Emulator): SystemPages {
  if (settings?.emulator === "Dolphin") return { pages: dolphinPages([settings, set]) };
  if (settings?.emulator === "Eden") return edenPages([settings, set]);
  if (settings?.emulator === "RetroArch") return { pages: retroarchPages([settings, set]) };
  return { pages: [] };
}

// The tile's toggle. While Steam adds or removes the tile, the toggle shows the asked state and a
// spinner turns 2em left of it. Steam draws the toggle: the spinner is placed from its box.
export function TileToggle({ system, game, label = "Show in Steam library", disabled }: {
  system: string; game: Game; label?: string; disabled?: boolean;
}) {
  const busy = useStore().busy[game.path];
  const change = busy?.startsWith("Showing") ? true : busy?.startsWith("Hiding") ? false : null;
  const row = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ right: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const toggle = row.current?.querySelector(`.${gamepadDialogClasses.Toggle}`);
    if (change == null || !row.current || !toggle) return setAt(null);
    const r = row.current.getBoundingClientRect();
    const t = toggle.getBoundingClientRect();
    setAt({ right: r.right - t.left, top: t.top + t.height / 2 - r.top });
  }, [change]);
  return (
    <div ref={row} className="rt-tilerow">
      <style>{PANEL_CSS}</style>
      <ToggleField label={label} checked={change ?? game.appid != null} disabled={disabled || !!busy || game.missing}
        onChange={(on) => toggleTile(system, game, on)} />
      {at && <span className="rt-rowspin" style={{ right: `calc(${at.right}px + 2em)`, top: at.top }}><Spinner /></span>}
    </div>
  );
}

// A game's Properties, laid out as Steam's: the pages in a column on the left, the shown page on the
// right. Every game has General, with its place in Steam and its emulator's language, then Images
// and Installed Files. Its system adds the pages of its emulator after General.
function Properties({ system, game }: { system: string; game: Game }) {
  const s = useStore();
  const files = useRomFiles(system, game);
  const settings = useEmulatorSettings(system, game);
  const sys = s.systems?.find((x) => x.id === system);
  const where = sys?.name ?? system;
  const shown = files?.files.slice(0, 8) ?? [];
  const added = systemPages(settings);
  const pages: PropertyPage[] = [
    {
      title: "General", identifier: "general", content: (
        <>
          <div className="rt-prop-heading">Steam</div>
          <TileToggle system={system} game={game} />
          {sys?.collection && <Field label="Collection">{sys.collection}</Field>}
          {added.language && (
            <>
              <div className="rt-prop-heading">Language</div>
              {added.language}
            </>
          )}
        </>
      ),
    },
    ...added.pages,
    {
      title: "Images", identifier: "images", content: KINDS.map((k) => (
        <Field key={k} label={KIND_LABEL[k]}>
          <DialogButton onClick={() => customize(system, game.path, k)}>Change…</DialogButton>
        </Field>
      )),
    },
    {
      title: "Installed Files", identifier: "files", content: (
        <>
          <Field label="Size on disk">{game.missing ? "ROM missing" : files ? formatSize(files.size) : "…"}</Field>
          {files && (
            <Field label={files.files.length === 1 ? "File" : `${files.files.length} files`} description={
              <div className="rt-files">
                {shown.map((f) => <div key={f}>{f}</div>)}
                {files.files.length > shown.length && <div>and {files.files.length - shown.length} more</div>}
              </div>
            } />
          )}
          {files && (
            <Field label="Uninstall">
              <DialogButton onClick={() => confirmUninstall(system, game, files, where, 2)}>Uninstall…</DialogButton>
            </Field>
          )}
        </>
      ),
    },
  ];
  return <SidebarNavigation title={game.name} showTitle pages={pages} />;
}

export function PropertiesPage() {
  const s = useStore();
  const selected = s.selected;
  const game = selected && findGame(selected.system, selected.path);
  // The Quick Access panel opens the page for a game whose system may not be listed yet.
  useEffect(() => {
    if (selected && !game) loadGames(selected.system);
  }, [selected?.path]);
  return <Page bare>{selected && game ? <Properties system={selected.system} game={game} /> : <SteamSpinner />}</Page>;
}
