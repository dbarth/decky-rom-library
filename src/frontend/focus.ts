// Steam keeps its gamepad focus in a navigation node of its own. The browser's focus() leaves that
// focus where it is: on the Odin 2 Portal, the gear kept it while Play had the browser's.

export interface NavNode {
  m_element: Element | null;
  BTakeFocus(): boolean;
}

interface Fiber {
  memoizedProps?: { node?: Partial<NavNode> } | null;
  return: Fiber | null;
}

// Returns the navigation node of an element that a Focusable or a DialogButton drew. The React
// fiber of the component that drew it holds the node in its 'node' prop. An ancestor's node is
// another element's.
export function navNode(el: Element): NavNode | null {
  const key = Object.keys(el).find((k) => k.startsWith("__reactFiber$"));
  for (let f = key ? (el as unknown as Record<string, Fiber>)[key] : null; f; f = f.return) {
    const node = f.memoizedProps?.node;
    if (node && typeof node.BTakeFocus === "function") return node.m_element === el ? node as NavNode : null;
  }
  return null;
}

// Gives Steam's gamepad focus to an element. Outside Steam, as in decky-vite, or when Steam refuses
// it, the browser's focus() does.
export function takeFocus(el: HTMLElement | null) {
  if (el && !navNode(el)?.BTakeFocus()) el.focus();
}

interface FocusNavController {
  UpdateSourceToGamepad?(force?: boolean): void;
}

// Shows Steam's focus as after a gamepad press. Steam shows it only while the last input came from the
// gamepad. On the Odin 2 Portal, the Quick Access menu opens over a game with a mouse move: the
// dialog it opens next keeps its focus unseen.
export function showGamepadFocus() {
  (globalThis as { FocusNavController?: FocusNavController }).FocusNavController?.UpdateSourceToGamepad?.(true);
}
