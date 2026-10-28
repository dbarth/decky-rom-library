// Hooks for decky-vite, the harness that serves the plugin's pages in a browser. decky-vite.json
// names this module.
import { refresh, state, update } from "../src/frontend/store";

// The Quick Access panel loads the systems before any page opens.
export function setup() {
  refresh();
}

// The plugin's place, kept across the harness's full reloads.
const KEPT = ["systemId", "selected", "query", "appsTab"] as const;

export const persist = {
  save: () => Object.fromEntries(KEPT.map((k) => [k, state[k]])),
  restore: (saved: object) => update(saved),
};
