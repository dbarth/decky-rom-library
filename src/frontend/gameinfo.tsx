import { Focusable } from "@decky/ui";
import { ReactNode, Ref } from "react";
import { usePicture } from "./hooks";
import { Game, Info } from "./tiles";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Writes a date as Steam does: "Sep 16, 2026", "Sep 2026" or "2026".
function formatDate(date: string): string {
  const [year, month, day] = date.split("-").map(Number);
  if (!month) return String(year);
  return day ? `${MONTHS[month - 1]} ${day}, ${year}` : `${MONTHS[month - 1]} ${year}`;
}

// The letters ESRB and CERO give for each minimum age.
const RATING_LETTERS: Record<string, Record<number, string>> = {
  ESRB: { 0: "E", 6: "E", 10: "E10+", 13: "T", 17: "M", 18: "AO" },
  CERO: { 0: "A", 12: "B", 15: "C", 17: "D", 18: "Z" },
};

function formatAges(ages: Record<string, number>): string | undefined {
  const shown = ["PEGI", "USK", "ESRB", "CERO"].filter((b) => ages[b] != null)
    .map((b) => `${b} ${RATING_LETTERS[b]?.[ages[b]] ?? ages[b]}`);
  return shown.length ? shown.join(", ") : undefined;
}

function formatPlayers(players: string): string {
  if (!/^\d+$/.test(players)) return `${players} players`;
  return players === "1" ? "Single-player" : `Up to ${players} players`;
}

const SOURCES: [string, string][] = [
  ["file", "game file"], ["name", "file name"], ["esde", "ES-DE"], ["fbneo", "FinalBurn Neo"],
  ["history", "Arcade-History"], ["libretro", "libretro"],
];

function PlayerIcon({ many }: { many: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      {many ? (
        <path d={"M8 3.5a3.5 3.5 0 1 1 0 7a3.5 3.5 0 1 1 0-7ZM1 20a7 7 0 0 1 14 0ZM16.5 4.5a3 3 0 1 1 0 6a3 3 0 0 1-1.6-.5"
          + "A5.5 5.5 0 0 0 15.2 5a3 3 0 0 1 1.3-.5ZM17 20a9 9 0 0 0-3.3-6.9A6 6 0 0 1 23 18.5V20Z"} />
      ) : (
        <path d="M12 3a4 4 0 1 1 0 8a4 4 0 1 1 0-8ZM4 21a8 8 0 0 1 16 0Z" />
      )}
    </svg>
  );
}

function PadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d={"M6.5 6h11a5.5 5.5 0 0 1 5.4 6.5l-.9 4.6a2.4 2.4 0 0 1-4.2 1.1L15.6 16H8.4l-2.2 2.2"
        + "a2.4 2.4 0 0 1-4.2-1.1l-.9-4.6A5.5 5.5 0 0 1 6.5 6ZM6 9v1.5H4.5v1.5H6v1.5h1.5V12H9v-1.5H7.5V9Z"
        + "M16.5 9.25a1.25 1.25 0 1 0 0 .01ZM18.75 11.5a1.25 1.25 0 1 0 0 .01Z"} />
    </svg>
  );
}

function StatusIcon({ ok }: { ok: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      {ok ? (
        <path fillRule="evenodd" d="M12 1a11 11 0 1 1 0 22a11 11 0 1 1 0-22ZM10.3 15.6l7.4-7.4-1.4-1.4-6 6-2.6-2.6-1.4 1.4Z" />
      ) : (
        <path fillRule="evenodd" d="M12 2 23 21H1ZM11 9v6h2V9ZM11 16.5v2h2v-2Z" />
      )}
    </svg>
  );
}

function ScreenIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path fillRule="evenodd" d="M7 1h10a2 2 0 0 1 2 2v18a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2ZM7.5 3.5v15h9v-15Z" />
    </svg>
  );
}

// A block of text the D-pad stops on, so that the page scrolls to it. Steam shows it focused with a
// faint background.
function Block({ className, children, focusRef }:
  { className?: string; children: ReactNode; focusRef?: Ref<HTMLDivElement> }) {
  return (
    <Focusable ref={focusRef} className={`rt-block${className ? " " + className : ""}`} focusClassName="rt-focus"
      noFocusRing {...({ focusable: true } as object)}>
      {children}
    </Focusable>
  );
}

// What Game Info shows: the description's paragraphs, history.xml's sections, the facts, what the
// game plays with, and the sources.
export interface Facts {
  paragraphs: string[];
  sections: [string, string][];
  facts: [string, string][];
  features: [ReactNode, string][];
  credit: string[];
}

export function factsOf(info: Info): Facts {
  const paragraphs = (info.description ?? "").split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const facts = ([
    ["Developer", info.developer],
    ["Publisher", info.publisher],
    ["Manufacturer", info.developer || info.publisher ? undefined : info.manufacturer],
    ["Release Date", info.released && formatDate(info.released)],
    ["Genre", info.genre],
    ["Board", info.board],
    ["Region", info.region],
    ["Languages", info.languages?.join(", ")],
    ["Game ID", info.serial],
    ["Version", info.version],
    ["Disc", info.disc != null ? String(info.disc) : undefined],
    ["Age Rating", info.ages && formatAges(info.ages)],
    ["Rating", info.rating != null ? `${Math.round(info.rating * 10) / 2} / 5` : undefined],
  ] as [string, string | undefined][]).filter((f): f is [string, string] => !!f[1]);
  const features: [ReactNode, string][] = [];
  if (info.players) features.push([<PlayerIcon many={info.players !== "1"} />, formatPlayers(info.players)]);
  const used = new Set(Object.values(info.sources ?? {}));
  if (used.has("fbneo")) {
    features.push([<StatusIcon ok={!info.broken} />, info.broken ? "Does not work in FinalBurn Neo" : "Works in FinalBurn Neo"]);
  }
  for (const c of info.controls ?? []) features.push([<PadIcon />, c]);
  // if (info.media) features.push([<PadIcon />, info.media]);
  if (info.vertical) features.push([<ScreenIcon />, "Vertical screen"]);
  const credit = SOURCES.filter(([k]) => used.has(k)).map(([, label]) => label);
  return { paragraphs, sections: info.sections ?? [], facts, features, credit };
}

export function hasFacts(f: Facts): boolean {
  return f.paragraphs.length + f.sections.length + f.facts.length + f.features.length > 0;
}

// An arcade game's second screen, laid out as Steam's Game Info: the capsule, then the name and the
// whole history, then what the game plays with and the facts. B or up from the top slides back.
export function GameInfo({ system, game, facts, firstRef, onBack }:
  { system: string; game: Game; facts: Facts; firstRef: Ref<HTMLDivElement>; onBack: () => void }) {
  const capsule = usePicture(system, game.path, "portrait");
  const [lead, ...rest] = facts.paragraphs;
  return (
    <div className="rt-gameinfo">
      <div className="rt-infobar" />
      <Focusable className="rt-infobody" flow-children="row" onCancelActionDescription="Back" onCancel={(e) => {
        e?.stopPropagation?.();
        onBack();
      }}>
        <div className="rt-infocapsule">{capsule && <img src={capsule} />}</div>
        <Focusable className="rt-history" flow-children="column">
          <Block focusRef={firstRef}>
            <h2>{game.name}</h2>
            {lead && <p>{lead}</p>}
          </Block>
          {rest.map((p, i) => <Block key={i}><p>{p}</p></Block>)}
          {facts.sections.map(([title, text]) => text.split(/\n\s*\n/).map((p, i) => (
            <Block key={`${title}-${i}`}>
              {i === 0 && <h3>{title}</h3>}
              <p>{p.trim()}</p>
            </Block>
          )))}
        </Focusable>
        <Block className="rt-infoside">
          {facts.features.length > 0 && (
            <div className="rt-features">
              {facts.features.map(([icon, label]) => <div key={label} className="rt-feature">{icon}{label}</div>)}
            </div>
          )}
          {facts.facts.length > 0 && (
            <dl className="rt-infofacts">{facts.facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          )}
          {facts.credit.length > 0 && <div className="rt-credit">Sources: {facts.credit.join(", ")}.</div>}
        </Block>
      </Focusable>
    </div>
  );
}
