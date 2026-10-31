// The parts of @decky/ui the game page loads. A Focusable and a DialogButton mark a preferred focus
// with data-preferred, and Navigation lists the routes it opens, for the tests to read.
import { ReactNode, Ref } from "react";

interface Props {
  children?: ReactNode;
  className?: string;
  disabled?: boolean;
  preferredFocus?: boolean;
  ref?: Ref<never>;
}

export function DialogButton({ children, className, disabled, preferredFocus, ref }: Props) {
  return (
    <button ref={ref} className={className} disabled={disabled} data-preferred={preferredFocus ? "" : undefined}>
      {children}
    </button>
  );
}

export function Focusable({ children, className, preferredFocus, ref }: Props) {
  return <div ref={ref} className={className} data-preferred={preferredFocus ? "" : undefined}>{children}</div>;
}

export const DialogButtonPrimary = DialogButton;
export const DialogButtonSecondary = DialogButton;

const Plain = ({ children }: Props) => <div>{children}</div>;
export const ButtonItem = Plain;
export const DialogBody = Plain;
export const DialogBodyText = Plain;
export const DialogFooter = Plain;
export const DialogHeader = Plain;
export const Field = Plain;
export const PanelSection = Plain;
export const PanelSectionRow = Plain;
export const ConfirmModal = Plain;
export const Menu = Plain;
export const MenuItem = Plain;
export const ModalRoot = Plain;
export const Tabs = Plain;
export const MenuSeparator = () => null;
export const SteamSpinner = () => null;
export const TextField = () => null;

export enum GamepadButton { BUMPER_LEFT = 11, BUMPER_RIGHT = 12 }
export const navigated: string[] = [];
export const Navigation = {
  Navigate: (route: string) => void navigated.push(route), NavigateBack: () => undefined, CloseSideMenus: () => undefined,
};
export const Router = { MainRunningApp: null, WindowStore: null };
export const gamepadTabbedPageClasses: Record<string, string> = new Proxy({}, { get: (_, key) => String(key) });
export const gamepadDialogClasses = gamepadTabbedPageClasses;
export const showContextMenu = () => undefined;
export const showModal = () => ({ Close: () => undefined });
