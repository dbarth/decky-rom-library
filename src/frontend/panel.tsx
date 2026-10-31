import {
  ButtonItem, DialogBody, DialogBodyText, DialogButton, DialogButtonPrimary, DialogButtonSecondary, DialogFooter,
  DialogHeader, Field, Focusable, ModalRoot, Navigation, PanelSection, PanelSectionRow, Router, showModal,
} from "@decky/ui";
import { ReactNode, useEffect, useReducer, useState } from "react";
import { LIBRARIES_ROUTE, openLibraries } from "./libraries";
import { GAMES_ROUTE, GAME_ROUTE, PROPERTIES_ROUTE, Spinner, openGames } from "./page";
import { TileToggle } from "./properties";
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

// The library's shown tab: its name, how many games or apps it holds, and a way to add more. A
// system's tab names the emulator its games start in.
function Section() {
  const s = useStore();
  const [places, setPlaces] = useState<{ downloads: string; loadout: boolean } | null>(null);
  useEffect(() => {
    getPlaces().then(setPlaces, () => undefined);
  }, []);
  if (s.appsTab) {
    const apps = s.games[APPS];
    return (
      <PanelSection title="Emulators">
        <PanelSectionRow>
          <Field label="Apps">{apps ? apps.length : "…"}</Field>
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
      </PanelSection>
    );
  }
  const system = s.systems?.find((x) => x.id === s.systemId);
  if (!system) return null;
  return (
    <PanelSection title={system.name}>
      <PanelSectionRow>
        <Field label="Emulator">{system.emulator}</Field>
      </PanelSectionRow>
      <PanelSectionRow>
        <Field label="Games">{system.games}</Field>
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
    </PanelSection>
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
function QuitModal({ game, appid, closeModal }: { game: Game; appid: number; closeModal?: () => void }) {
  const quitting = useStore().busy[game.path] === "Quitting…";
  const [asked, setAsked] = useState(false);
  useEffect(() => {
    if (asked && !quitting) closeModal?.();
  }, [asked, quitting]);
  return (
    <ModalRoot closeModal={closeModal} onCancel={closeModal}>
      <style>{PANEL_CSS}</style>
      <DialogHeader>Quit game?</DialogHeader>
      <DialogBody>
        <DialogBodyText>Unsaved game data may be lost.</DialogBodyText>
      </DialogBody>
      <DialogFooter>
        <Focusable flow-children="row" style={{ display: "flex", gap: "12px" }}>
          <DialogButtonPrimary className={quitting ? "rt-quit rt-pending" : "rt-quit"} style={{ flex: 1 }}
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

// A game's state, a link to its Properties and its tile's toggle, and Quit Game for the game that
// runs under the app id running. Steam gives the focus to the panel's first row.
function GameLink({ shown, running }: { shown: GameRef; running: number | null }) {
  const s = useStore();
  const game = findGame(shown.system, shown.path);
  useEffect(() => {
    if (!state.games[shown.system]) loadGames(shown.system);
  }, [shown.path]);
  if (!game) return null;
  const quitting = s.busy[game.path] === "Quitting…";
  return (
    <PanelSection title={running != null ? "Running Game" : "Library Page"}>
      <PanelSectionRow>
        <Field label={<span className="rt-gamename">{game.name}</span>} />
      </PanelSectionRow>
      <PanelSectionRow>
        {/* Steam tracks a running game by its tile, which must stay while the game runs. */}
        <TileToggle system={shown.system} game={game} label="Show in Steam"
          disabled={running != null && game.appid != null} />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => {
          update({ selected: shown });
          Navigation.CloseSideMenus();
          Navigation.Navigate(PROPERTIES_ROUTE);
        }}>
          Properties…
        </ButtonItem>
      </PanelSectionRow>
      {running != null && (
        <PanelSectionRow>
          <Field childrenLayout="below" childrenContainerWidth="max">
            <style>{PANEL_CSS}</style>
            <DialogButton className={quitting ? "rt-quit rt-pending" : "rt-quit"} disabled={quitting}
              onClick={() => confirmQuit(game, running)}>
              <span className="rt-text">Quit Game</span>
              {quitting && <Spinner />}
            </DialogButton>
          </Field>
        </PanelSectionRow>
      )}
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

// The section of the game that runs, and the section of the game of the page under the panel when
// it is another one: the game of our game page or its Properties, or the tile of Steam's page. The
// store's change at the end of Quit Game draws them again without the game.
function useGames(route: string): { running: ReactNode; page: ReactNode } {
  useStore();
  const pageId = Number(route.match(/^\/library\/app\/(\d+)/)?.[1]) || null;
  const app = useRunningApp();
  const pageInfo = useAppInfo(pageId);
  const runningInfo = useAppInfo(app ? Number(app.appid) : null);
  // useAppInfo keeps the last app's info once no game runs.
  const playing = app ? gameOf(runningInfo, state.playing) : null;
  const ours = route === GAME_ROUTE || route === PROPERTIES_ROUTE;
  const shown = ours ? state.selected : gameOf(pageInfo, null);
  return {
    running: app && playing && <GameLink shown={playing} running={Number(app.appid)} />,
    page: shown && shown.path !== playing?.path && <GameLink shown={shown} running={null} />,
  };
}

// Opens the library. Until the user chooses a library, opens the libraries page.
function openLibrary() {
  getPlaces().then((p) => (p.roots ? openGames() : openLibraries(true)), () => openGames());
}

// Shows the Quick Access panel: what the plugin does, Open Library when the library is closed, the
// library's tab, Scan Libraries…, then the games. One of our games that runs outside the library takes
// the panel alone. Opening the panel brings the tiles in line with the ROM folders.
export function Panel() {
  const route = mainRoute();
  useEffect(() => {
    refresh();
  }, []);
  const games = useGames(route);
  const inLibrary = route.startsWith(GAMES_ROUTE);
  if (games.running && !inLibrary) {
    return (
      <>
        {games.running}
        {games.page}
      </>
    );
  }
  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          <Field description="Play, manage and surface console games in your Steam Library" />
        </PanelSectionRow>
      </PanelSection>
      {!inLibrary && (
        <PanelSection>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={openLibrary}>Open Library</ButtonItem>
          </PanelSectionRow>
        </PanelSection>
      )}
      {route === GAMES_ROUTE && <Section />}
      {route !== LIBRARIES_ROUTE && (
        <PanelSection>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => openLibraries()}>Scan Libraries…</ButtonItem>
          </PanelSectionRow>
        </PanelSection>
      )}
      {games.running}
      {games.page}
    </>
  );
}
