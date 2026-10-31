import {
  ButtonItem, DialogBody, DialogBodyText, DialogButton, DialogButtonPrimary, DialogButtonSecondary, DialogFooter,
  DialogHeader, Field, Focusable, ModalRoot, Navigation, PanelSection, PanelSectionRow, Router, gamepadDialogClasses,
  showModal,
} from "@decky/ui";
import { ReactNode, useEffect, useReducer, useRef, useState } from "react";
import { takeFocus } from "./focus";
import { LIBRARIES_ROUTE, openLibraries } from "./libraries";
import { GAMES_ROUTE, GAME_ROUTE, PROPERTIES_ROUTE, Spinner, openGames } from "./page";
import { addGame, findGame, loadGames, quit, refresh, state, update, useStore } from "./store";
import { PANEL_CSS } from "./styles";
import { APPS, AppInfo, Game, describeApp, getPlaces } from "./tiles";

// Loadout's page, when its plugin is installed.
const LOADOUT_ROUTE = "/loadout";

// The route of Steam's main window, such as /library/app/<appid> or /rom-library/game. @decky/ui
// does not type its history.
function mainRoute(): string {
  const main = Router.WindowStore?.GamepadUIMainWindowInstance as { m_history?: { location?: { pathname?: string } } };
  return main?.m_history?.location?.pathname ?? "";
}

// What the plugin knows of an app: undefined while it asks.
function useAppInfo(appid: number | null): AppInfo | null | undefined {
  const [info, setInfo] = useState<AppInfo | null | undefined>(undefined);
  useEffect(() => {
    if (appid != null) describeApp(appid).then(setInfo, () => setInfo(null));
  }, [appid]);
  return info;
}

// Says what the plugin does, under the panel's title.
function Intro() {
  return (
    <div className={`${gamepadDialogClasses.FieldDescription} rt-intro`}>
      Play and manage console games in your Steam Library
    </div>
  );
}

// Opens the library. Until the user chooses a library, opens the libraries page.
function openLibrary() {
  getPlaces().then((p) => (p.roots ? openGames() : openLibraries(true)), () => openGames());
}

function OpenLibrary() {
  return (
    <PanelSectionRow>
      <ButtonItem layout="below" onClick={openLibrary}>Open Library</ButtonItem>
    </PanelSectionRow>
  );
}

function ScanLibraries() {
  return (
    <PanelSectionRow>
      <ButtonItem layout="below" onClick={() => openLibraries()}>Scan Libraries…</ButtonItem>
    </PanelSectionRow>
  );
}

// Shows the tab's rows: a system's games and Add a Game…, or the emulators and Add Emulators… when
// Loadout is installed.
function TabRows() {
  const s = useStore();
  const [places, setPlaces] = useState<{ downloads: string; loadout: boolean } | null>(null);
  useEffect(() => {
    getPlaces().then(setPlaces, () => undefined);
  }, []);
  if (s.appsTab) {
    const apps = s.games[APPS];
    return (
      <>
        <PanelSectionRow>
          <Field label="Emulators">{apps ? apps.length : "…"}</Field>
        </PanelSectionRow>
        {places?.loadout && (
          <PanelSectionRow>
            <ButtonItem layout="below" description="Install emulators and apps with Loadout" onClick={() => {
              Navigation.CloseSideMenus();
              Navigation.Navigate(LOADOUT_ROUTE);
            }}>
              Add Emulators…
            </ButtonItem>
          </PanelSectionRow>
        )}
      </>
    );
  }
  const system = s.systems?.find((x) => x.id === s.systemId);
  if (!system) return null;
  return (
    <>
      <PanelSectionRow>
        <Field label={system.name}>{system.games}</Field>
      </PanelSectionRow>
      {places && (
        <PanelSectionRow>
          <ButtonItem layout="below" description={`Move a game from Downloads into the ${system.name} folder`}
            onClick={() => {
              Navigation.CloseSideMenus();
              addGame(system, places.downloads).catch(() => undefined);
            }}>
            Add a Game…
          </ButtonItem>
        </PanelSectionRow>
      )}
    </>
  );
}

type GameRef = { system: string; path: string };

// The game of a tile, or the last game started for the hidden launcher.
function gameOf(info: AppInfo | null | undefined, launched: GameRef | null): GameRef | null {
  if (!info) return null;
  if ("tile" in info) return { system: info.system, path: info.tile };
  return info.kind === "launcher" ? launched : null;
}

// Steam's Exit Game dialog, titled Quit game? to tell the two apart. Confirm has the focus and spins
// until Steam no longer runs the game, then the dialog closes. B or a click beside the dialog closes
// it sooner: the game still quits, and the panel's Quit Game spins.
export function QuitModal({ game, appid, closeModal }: { game: Game; appid: number; closeModal?: () => void }) {
  const quitting = useStore().busy[game.path] === "Quitting…";
  const [asked, setAsked] = useState(false);
  useEffect(() => {
    if (asked && !quitting) closeModal?.();
  }, [asked, quitting]);
  // Confirm takes Steam's focus when the dialog opens. The dialog opens as the Quick Access panel
  // closes: Confirm takes the focus again when the dialog's window gets it back.
  const confirm = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = confirm.current;
    const win = el?.ownerDocument.defaultView;
    const again = () => takeFocus(el);
    takeFocus(el);
    win?.addEventListener("focus", again, { once: true });
    return () => win?.removeEventListener("focus", again);
  }, []);
  return (
    <ModalRoot closeModal={closeModal} onCancel={closeModal}>
      <style>{PANEL_CSS}</style>
      <DialogHeader>Quit game?</DialogHeader>
      <DialogBody>
        <DialogBodyText>Unsaved game data may be lost.</DialogBodyText>
      </DialogBody>
      <DialogFooter>
        <Focusable flow-children="row" style={{ display: "flex", gap: "12px" }}>
          <DialogButtonPrimary ref={confirm} className={quitting ? "rt-quit rt-pending" : "rt-quit"} style={{ flex: 1 }}
            preferredFocus onClick={() => {
              if (quitting) return;
              setAsked(true);
              quit(game, appid);
            }}>
            <span className="rt-text">Confirm</span>
            {quitting && <Spinner />}
          </DialogButtonPrimary>
          <DialogButtonSecondary style={{ flex: 1 }} disabled={quitting} onClick={closeModal}>
            Cancel
          </DialogButtonSecondary>
        </Focusable>
      </DialogFooter>
    </ModalRoot>
  );
}

// Asks before quitting the game, as Steam does before Exit Game: the panel closes and the dialog
// shows over the game.
function confirmQuit(game: Game, appid: number) {
  Navigation.CloseSideMenus();
  showModal(<QuitModal game={game} appid={appid} />);
}

// Returns a game of the library, and loads its system's games when the store lacks them.
function useGame(shown: GameRef): Game | undefined {
  useStore();
  useEffect(() => {
    if (!state.games[shown.system]) loadGames(shown.system);
  }, [shown.path]);
  return findGame(shown.system, shown.path);
}

function GameName({ game }: { game: Game }) {
  return (
    <PanelSectionRow>
      <Field label={<span className="rt-gamename">{game.name}</span>} />
    </PanelSectionRow>
  );
}

function PropertiesButton({ shown }: { shown: GameRef }) {
  return (
    <PanelSectionRow>
      <ButtonItem layout="below" onClick={() => {
        update({ selected: shown });
        Navigation.CloseSideMenus();
        Navigation.Navigate(PROPERTIES_ROUTE);
      }}>
        Properties…
      </ButtonItem>
    </PanelSectionRow>
  );
}

// Shows the game of the page under the panel, with Properties….
function GamePage({ shown }: { shown: GameRef }) {
  const game = useGame(shown);
  if (!game) return null;
  return (
    <PanelSection>
      <GameName game={game} />
      <PropertiesButton shown={shown} />
    </PanelSection>
  );
}

// Shows the game that runs under the app id, with Properties… and Quit Game. Steam gives the focus to
// the panel's first row.
function RunningGame({ shown, appid }: { shown: GameRef; appid: number }) {
  const game = useGame(shown);
  const quitting = useStore().busy[shown.path] === "Quitting…";
  if (!game) return null;
  return (
    <PanelSection title="Running Game">
      <GameName game={game} />
      <PropertiesButton shown={shown} />
      <PanelSectionRow>
        <Field childrenLayout="below" childrenContainerWidth="max">
          <DialogButton className={quitting ? "rt-quit rt-pending" : "rt-quit"} disabled={quitting}
            onClick={() => confirmQuit(game, appid)}>
            <span className="rt-text">Quit Game</span>
            {quitting && <Spinner />}
          </DialogButton>
        </Field>
      </PanelSectionRow>
    </PanelSection>
  );
}

// The app Steam runs. Steam keeps the panel mounted while a game starts or ends from its own tile:
// its notice draws the panel again, then once more 1 s later, in case Router has not caught up yet.
function useRunningApp() {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    const notices = SteamClient.GameSessions.RegisterForAppLifetimeNotifications(() => {
      bump();
      setTimeout(bump, 1000);
    });
    return () => notices.unregister();
  }, []);
  return Router.MainRunningApp;
}

// Returns the game of ours that runs, with its app id, and the game of the page under the panel: our
// game page's, or the tile of Steam's page. The store's change at the end of Quit Game draws the panel
// again without the game.
function useGames(route: string): { running: { shown: GameRef; appid: number } | null; page: GameRef | null } {
  useStore();
  const pageId = Number(route.match(/^\/library\/app\/(\d+)/)?.[1]) || null;
  const app = useRunningApp();
  const pageInfo = useAppInfo(pageId);
  const runningInfo = useAppInfo(app ? Number(app.appid) : null);
  // useAppInfo keeps the last app's info once no game runs.
  const playing = app ? gameOf(runningInfo, state.playing) : null;
  return {
    running: app && playing ? { shown: playing, appid: Number(app.appid) } : null,
    page: route === GAME_ROUTE ? state.selected : gameOf(pageInfo, null),
  };
}

// Shows the Quick Access panel in one of four modes. A running game of ours takes the panel alone,
// with Properties… and Quit Game. A game page shows its game's Properties…. The library and a game's
// Properties show the tab's tools and Scan Libraries…. Elsewhere, the panel shows Open Library and
// Scan Libraries…. The libraries page shows the intro alone. Opening the panel brings the tiles in
// line with the ROM folders.
export function Panel() {
  const route = mainRoute();
  useEffect(() => {
    refresh();
  }, []);
  const { running, page } = useGames(route);
  let tools: ReactNode;
  if (running) {
    tools = <RunningGame shown={running.shown} appid={running.appid} />;
  } else if (page) {
    tools = <GamePage shown={page} />;
  } else if (route.startsWith(GAMES_ROUTE)) {
    tools = route !== LIBRARIES_ROUTE && (
      <PanelSection>
        <TabRows />
        <ScanLibraries />
      </PanelSection>
    );
  } else {
    tools = (
      <PanelSection>
        <OpenLibrary />
        <ScanLibraries />
      </PanelSection>
    );
  }
  return (
    <>
      <style>{PANEL_CSS}</style>
      {!running && <Intro />}
      {tools}
    </>
  );
}
