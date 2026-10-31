import { Library, NewLibrary } from "./tiles";

// Sample libraries for the libraries page's scenarios, to review each screen without a scan.
export type Scenario = "searching" | "none" | "one" | "several" | "exfat" | "organizer";

const systems = (list: [string, string, number][]) => list.map(([id, name, games]) => ({ id, name, games }));

const SD: Library = {
  path: "/run/media/steamos/MicroSD/Emulation/roms", where: "MicroSD/Emulation/roms",
  drive: { kind: "sd", name: "MicroSD Card" }, fs: "exfat", links: false, usedBy: ["Loadout"], games: 1284,
  systems: systems([["snes", "SNES", 412], ["gb", "Game Boy", 340], ["megadrive", "Mega Drive", 230],
    ["gba", "GBA", 148], ["psx", "PlayStation", 96], ["nes", "NES", 58]]),
};

const INTERNAL: Library = {
  path: "/home/steamos/Emulation/roms", where: "~/Emulation/roms",
  drive: { kind: "internal", name: "Internal Storage" }, fs: "ext4", links: true, usedBy: ["ES-DE"], games: 194,
  systems: systems([["fbneo", "Arcade", 160], ["c64", "C64", 19], ["n64", "N64", 4], ["dreamcast", "Dreamcast", 3],
    ["psp", "PSP", 3], ["switch", "Switch", 2], ["wii", "Wii", 2], ["gc", "GameCube", 1]]),
};

const USB: Library = {
  path: "/run/media/steamos/GAMES/roms", where: "GAMES/roms", drive: { kind: "usb", name: "GAMES" },
  fs: "exfat", links: false, usedBy: [], games: 20,
  systems: systems([["snes", "SNES", 12], ["gba", "GBA", 5], ["nes", "NES", 3]]),
};

// The libraries a scenario's scan finds.
export function sampleLibraries(scenario: Scenario): Library[] {
  switch (scenario) {
    case "one": return [INTERNAL];
    case "several": case "organizer": return [SD, INTERNAL, USB];
    case "exfat": return [SD, USB];
    default: return [];
  }
}

const FOLDERS = [["fbneo", "Arcade"], ["snes", "SNES"], ["nes", "NES"], ["gba", "GBA"], ["megadrive", "Mega Drive"],
  ["psx", "PlayStation"], ["n64", "N64"], ["dreamcast", "Dreamcast"], ["psp", "PSP"], ["switch", "Switch"],
  ["wii", "Wii"], ["c64", "C64"]].map(([id, name]) => ({ id, name }));

export const SAMPLE_PLACES: NewLibrary[] = [
  { path: INTERNAL.path, drive: INTERNAL.drive, free: 40 * 1024 ** 3, systems: FOLDERS },
  { path: SD.path, drive: SD.drive, free: 412 * 1024 ** 3, systems: FOLDERS },
];
