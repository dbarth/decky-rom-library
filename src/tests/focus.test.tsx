// Tests that a game's page opens with Steam's focus on Play, and the quit dialog on Confirm. Run with:
// npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { navigated } from "@decky/ui";
import { navNode, showGamepadFocus, takeFocus } from "../frontend/focus";
import { GameView, PROPERTIES_ROUTE, openProperties } from "../frontend/page";
import { QuitModal } from "../frontend/panel";
import { APPS, Game } from "../frontend/tiles";

const GAME: Game = { path: "/roms/fbneo/1942.zip", file: "1942.zip", name: "1942", appid: null, thumb: null,
  favorite: false, missing: false };
const APP: Game = { ...GAME, path: "app:1", file: "", name: "Eden", kind: "emulator" };

// Returns the opening tags of the elements that ask for the first focus.
function preferred(element: ReactElement): string[] {
  const html = renderToStaticMarkup(element);
  return [...html.matchAll(/<[a-z]+ [^>]*data-preferred[^>]*>/g)].map((m) => m[0]);
}

test("a game's page prefers Play, and no other element", () => {
  const found = preferred(<GameView system="fbneo" game={GAME} />);
  assert.equal(found.length, 1, found.join("\n"));
  assert.match(found[0], /rt-play/);
});

test("an app's page prefers the gear, and no other element", () => {
  const found = preferred(<GameView system={APPS} game={APP} />);
  assert.equal(found.length, 1, found.join("\n"));
  assert.match(found[0], /rt-gear/);
});

test("the quit dialog prefers Confirm, and no other element", () => {
  const found = preferred(<QuitModal game={GAME} appid={1} />);
  assert.equal(found.length, 1, found.join("\n"));
  assert.match(found[0], /rt-quit/);
});

// An element as Steam draws it: the React fiber of its component holds Steam's navigation node.
function steamElement(took: boolean) {
  const calls: string[] = [];
  const el = { focus: () => calls.push("browser") } as unknown as HTMLElement & Record<string, unknown>;
  const node: { m_element: object; BTakeFocus(): boolean } = {
    m_element: el, BTakeFocus: () => (calls.push("steam"), took),
  };
  el["__reactFiber$test"] = { memoizedProps: { className: "x" }, return: { memoizedProps: { node }, return: null } };
  return { el, node, calls };
}

test("takeFocus gives Steam's focus through the element's own node", () => {
  const { el, node, calls } = steamElement(true);
  assert.equal(navNode(el), node);
  takeFocus(el);
  assert.deepEqual(calls, ["steam"]);
});

test("takeFocus falls back to the browser's focus when Steam refuses it", () => {
  const { el, calls } = steamElement(false);
  takeFocus(el);
  assert.deepEqual(calls, ["steam", "browser"]);
});

test("takeFocus ignores an ancestor's node, and uses the browser's focus outside Steam", () => {
  const { el, node, calls } = steamElement(true);
  node.m_element = {};
  assert.equal(navNode(el), null);
  takeFocus(el);
  const plain = { focus: () => calls.push("plain") } as unknown as HTMLElement;
  takeFocus(plain);
  assert.deepEqual(calls, ["browser", "plain"]);
});

test("the gear hands Steam's focus to Play before it opens Properties", () => {
  const { el, node } = steamElement(true);
  let opened = -1;
  node.BTakeFocus = () => ((opened = navigated.length), true);
  navigated.length = 0;
  openProperties(el);
  assert.equal(opened, 0);
  assert.deepEqual(navigated, [PROPERTIES_ROUTE]);
});

test("showGamepadFocus switches Steam's navigation source to the gamepad, and does nothing outside Steam", () => {
  const calls: unknown[] = [];
  const g = globalThis as { FocusNavController?: unknown };
  showGamepadFocus();
  g.FocusNavController = { UpdateSourceToGamepad: (force: boolean) => calls.push(force) };
  try {
    showGamepadFocus();
  } finally {
    delete g.FocusNavController;
  }
  assert.deepEqual(calls, [true]);
});
