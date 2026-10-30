import { staticClasses } from "@decky/ui";
import { definePlugin, routerHook } from "@decky/api";
import { LIBRARIES_ROUTE, LibrariesPage } from "./libraries";
import { GAMES_ROUTE, GAME_ROUTE, GamePage, GamesPage, PROPERTIES_ROUTE } from "./page";
import { Panel } from "./panel";
import { PropertiesPage } from "./properties";

function Icon() {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor">
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  );
}

export default definePlugin(() => {
  routerHook.addRoute(GAMES_ROUTE, GamesPage, { exact: true });
  routerHook.addRoute(GAME_ROUTE, GamePage, { exact: true });
  routerHook.addRoute(PROPERTIES_ROUTE, PropertiesPage, { exact: true });
  routerHook.addRoute(LIBRARIES_ROUTE, LibrariesPage, { exact: true });
  return {
    name: "ROM Library",
    titleView: <div className={staticClasses.Title}>ROM Library</div>,
    content: <Panel />,
    icon: <Icon />,
    onDismount() {
      routerHook.removeRoute(GAMES_ROUTE);
      routerHook.removeRoute(GAME_ROUTE);
      routerHook.removeRoute(PROPERTIES_ROUTE);
      routerHook.removeRoute(LIBRARIES_ROUTE);
    },
  };
});
