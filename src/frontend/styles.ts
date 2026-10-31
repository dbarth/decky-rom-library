import { gamepadTabbedPageClasses } from "@decky/ui";

// The rules the Quick Access panel shares with the pages: the spinner, the tile's toggle, the busy
// button and the running game's name. The panel shares the document with Steam's pages, so it takes
// these rules alone.
export const PANEL_CSS = `
/* The running game's name stands above its section's grey title. */
.rt-gamename { font-size: 18px; font-weight: 600; color: #fff; }
/* The spinner takes the colour of the text: dark on a focused button, light elsewhere. */
.rt-spin { position: absolute; top: 50%; left: 50%; box-sizing: border-box; width: 22px; height: 22px;
  margin: -11px 0 0 -11px; border: 3px solid color-mix(in srgb, currentColor 33%, transparent);
  border-top-color: currentColor; border-radius: 50%; animation: rt-spin 0.8s linear infinite; }
@keyframes rt-spin { to { transform: rotate(360deg); } }
/* A busy button hides its label under the spinner. */
.rt-quit { position: relative; }
.rt-pending .rt-text { visibility: hidden; }
/* The spinner turns 2em left of the tile's toggle, centred on it. */
.rt-tilerow { position: relative; }
.rt-rowspin { position: absolute; width: 22px; height: 22px; margin-top: -11px; pointer-events: none; }
`;

// The styles of every page and dialog: the type scale and the colours, then the rules of each page.
export const CSS = `
.rt-page, .rt-modal {
  --rt-display: 48px; --rt-title: 32px; --rt-heading: 18px; --rt-body: 16px; --rt-meta: 14px; --rt-label: 14px;
  --rt-ink: #dcdedf; --rt-dim: #8b929a; --rt-card: #1f252e; --rt-bar: #171d25; --rt-line: #2a313b;
  color: var(--rt-ink);
}
.rt-page { height: 100%; display: flex; flex-direction: column; background: #0e141b; color: var(--rt-ink); }
/* The bar takes the 40px row of Steam's status bar, whose veil goes while the page is shown. Steam's
   icons and its search glyph keep the right 306px of the row. */
#header { --gamepadui-header-background-opacity: 0 !important; }
/* Steam keeps the default content-box: the boxes here with a size and a padding set border-box.
   The title and the text of the field share a baseline. The top padding centres the field in the row. */
.rt-bar { flex: none; box-sizing: border-box; height: 40px; display: flex; align-items: baseline; gap: 24px;
  padding: 6px 320px 0 2.8vw; background: var(--rt-bar); border-bottom: 1px solid var(--rt-line); }
.rt-brand { flex: none; display: flex; align-items: baseline; gap: 10px; font-size: var(--rt-heading); font-weight: 800;
  color: #fff; }
/* The logo is as tall as the title's capitals and rests on its baseline. */
.rt-brand svg { width: 12px; height: 12px; }
.rt-search { flex: none; position: relative; width: 300px; }
.rt-search > svg { position: absolute; left: 10px; top: 50%; width: 14px; height: 14px; margin-top: -7px;
  color: var(--rt-dim); pointer-events: none; z-index: 1; }
/* Steam's input rules outweigh a class. */
.rt-search input { box-sizing: border-box; height: 28px !important; padding: 4px 10px 4px 32px !important; font-size: var(--rt-meta) !important; }
.rt-body { flex: 1; min-height: 0; position: relative; }
/* The grid scrolls under the console tabs: their row takes the footer's blurred veil. */
.rt-page .${gamepadTabbedPageClasses.TabHeaderRowWrapper} { background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(100px); }
.rt-scroll { height: 100%; overflow-y: auto; }
.rt-content { padding: 24px 2.8vw 64px; }
.rt-tab { padding: 16px 0 64px; }
.rt-grid { display: grid; gap: 24px 20px; }
/* Steam's library grid: a capsule width set by the window size, 42px from one row of capsules to
   the next, 16px at least between columns, and the free width spread between the columns. The
   26px of the name and a 16px gap make the 42px. */
.rt-games { --rt-tile: 134px; grid-template-columns: repeat(auto-fill, var(--rt-tile)); justify-content: space-between;
  gap: 16px; padding: 8px; }
@media (min-width: 1280px) { .rt-games { --rt-tile: 172px; } }
@media (max-width: 853px), (max-height: 500px) { .rt-games { --rt-tile: 110px; } }
.rt-art-portrait { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
.rt-art-landscape { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.rt-art-hero { grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
.rt-art-logo { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }
.rt-art-icon { grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); }
.rt-card { position: relative; border-radius: 6px; background: var(--rt-card); overflow: hidden; }
.rt-media { position: relative; }
.rt-frame { position: relative; width: 100%; overflow: hidden; background: #000; }
.rt-frame img { position: absolute; inset: 0; width: 100%; height: 100%; }
.rt-backdrop { object-fit: cover; filter: blur(8px) brightness(0.55); transform: scale(1.15); }
.rt-fit { object-fit: contain; }
.rt-logo .rt-frame { background: #3d4450; }
.rt-logo .rt-fit { inset: 8%; width: 84%; height: 84%; }
/* A game or an app in the grid looks like a Steam capsule, with its name under it, and takes the
   focus of Steam's library. scale(1.0526) draws Steam's translateZ(15px) in a 300px perspective.
   Steam draws the focus ring around the image: the card names it in focusRingSizeElementID. */
.rt-card.rt-capsule { background: none; overflow: visible; border-radius: 0; }
.rt-capsule .rt-media { overflow: hidden; filter: brightness(0.9); box-shadow: 0 4px 10px #00000040;
  transition: transform 0.1s cubic-bezier(0.16, 0.86, 0.43, 0.99); }
.rt-capsule.rt-focus .rt-media { transform: scale(1.0526); filter: none; box-shadow: 0 16px 24px #00000080;
  transition-duration: 0.3s; }
/* A light band crosses the focused capsule once and leaves a faint sheen. */
.rt-capsule .rt-media::after { content: ""; position: absolute; inset: 0; z-index: 2; pointer-events: none;
  background: linear-gradient(-45deg, #ffffff33 30%, #ffffff4d 36%, #aaa 49%, #ccc 51%, #ffffff4d 64%, #ffffff33 70%)
    0 0 / 300% 100%;
  mix-blend-mode: overlay; opacity: 0; transition: opacity 0.1s cubic-bezier(0.16, 0.86, 0.43, 0.99); }
.rt-capsule.rt-focus .rt-media::after { background-position: -180% 0; opacity: 0.8; animation: rt-shine 1s backwards;
  transition: opacity 0.3s cubic-bezier(0.17, 0.45, 0.14, 0.83); }
@keyframes rt-shine { from { background-position: 0 0; opacity: 1; } }
.rt-capsule .rt-badge { z-index: 3; }
.rt-capsule .rt-name { padding: 8px 2px 0; font-size: var(--rt-meta); line-height: 18px; color: var(--rt-dim); }
.rt-capsule.rt-focus .rt-name { color: #fff; }
.rt-capsule .rt-sub { padding: 2px 2px 0; min-height: 0; }
.rt-name { font-size: var(--rt-body); padding: 10px 12px 2px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.rt-sub { font-size: var(--rt-meta); color: var(--rt-dim); padding: 0 12px 10px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; min-height: 1.2em; }
.rt-label { font-size: var(--rt-meta); color: var(--rt-dim); padding: 8px 12px 10px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.rt-badge { position: absolute; bottom: 8px; right: 8px; padding: 4px 6px; border-radius: 3px;
  background: #dcdedf; color: #0e141b; font-size: var(--rt-label); font-weight: 700; line-height: 1; }
.rt-badge.rt-in-steam { padding: 4px; }
.rt-in-steam svg { display: block; width: 12px; height: 12px; }
.rt-empty { padding: 24px 0; font-size: var(--rt-body); color: var(--rt-dim); }
/* The game page: the hero art from the top of the screen, as tall as Steam's on an app page, then
   Play, the facts and the two settings buttons in one row. The page fills the screen. An arcade
   game's Game Info waits under it as a second screen and slides up. Steam's focus scrolling cannot
   move a clipped box: only the slide moves the screens. */
.rt-pages { --rt-hero: calc(80px + 20vw); --rt-left: 2.8vw; height: 100%; overflow: hidden; overflow: clip; }
.rt-track { height: 100%; transition: transform 0.45s cubic-bezier(0.16, 0.86, 0.43, 0.99); }
.rt-track.rt-open { transform: translateY(-100%); }
.rt-game { height: 100%; }
.rt-hero { position: relative; height: var(--rt-hero); overflow: hidden; background: #000; }
/* A hero of another shape fills the width without distortion, centred vertically. A wider one fills
   the height, centred across. */
.rt-hero > img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center; }
.rt-hero::after { content: ""; position: absolute; inset: 0; }
/* The badge rests on the title's last baseline, its right edge in line with the gear's. */
.rt-headline { position: absolute; z-index: 1; left: var(--rt-left); right: 2.8vw; bottom: 16px; display: flex;
  align-items: last baseline; gap: 24px; }
.rt-headline > :first-child { min-width: 0; }
.rt-steam { flex: none; margin-left: auto; display: flex; align-items: baseline; gap: 6px; padding: 5px 8px;
  border-radius: 3px; background: #dcdedf; color: #0e141b; font-size: var(--rt-label); font-weight: 700; line-height: 1; }
.rt-steam svg { width: 10px; height: 10px; }
.rt-hero > img { animation: rt-fade 0.2s ease-out; }
.rt-hero > .rt-slide { animation: rt-fade 1.5s ease-in-out; }
@keyframes rt-fade { from { opacity: 0; } }
.rt-title { font-size: var(--rt-display); font-weight: 800; color: #fff; line-height: 1.15; text-shadow: 0 2px 8px #000c; }
.rt-strip { position: relative; padding: 16px 2.8vw 16px var(--rt-left); }
/* The veil fades in after 0.4s: a quick change ends before it shows. */
.rt-tile-busy { position: absolute; inset: 0; background: #0008; animation: rt-fade 0.2s ease-out 0.4s backwards; }
.rt-actions { display: flex; align-items: center; gap: 24px; }
.rt-tools { display: flex; gap: 8px; }
.rt-actions .rt-act { flex: none; position: relative; height: 56px; padding: 0 16px; }
.rt-actions .rt-act.rt-big { width: auto; min-width: 180px; padding: 0 16px !important; text-align: left; font-size: 20px;
  font-weight: 700; }
.rt-actions .rt-act.rt-play { color: #fff !important; }
.rt-big .rt-text { display: flex; align-items: center; }
.rt-big svg { width: 24px; height: 24px; margin-right: 16px; }
/* Play stays grey until focused, then turns Steam's plain green, and a band of light runs once
   around its 2px edge. The other buttons keep Steam's white focus. Steam's button rules outweigh a
   class. */
.rt-actions .rt-act.rt-play.gpfocus { background: #59bf40 !important; }
.rt-actions .rt-act.rt-play.gpfocus::after { content: ""; position: absolute; inset: 0; border-radius: 2px; pointer-events: none;
  background: linear-gradient(75deg, #59bf4000 33%, #bde5b3 50%, #59bf4000 66%) 0 0 / 300% 100%; opacity: 0;
  clip-path: polygon(0 0, 0 100%, 2px 100%, 2px 2px, calc(100% - 2px) 2px, calc(100% - 2px) calc(100% - 2px),
    2px calc(100% - 2px), 2px 100%, 100% 100%, 100% 0);
  animation: rt-edge 2s; }
@keyframes rt-edge { from { background-position: 0 0; opacity: 1; } to { background-position: -180% 0; opacity: 0.8; } }
/* Steam's padding outweighs a class: the icon buttons drop it here, with Steam's 160px minimum width. */
.rt-actions .rt-act.rt-icon { width: 48px; min-width: 0; height: 48px; padding: 0 !important; display: flex;
  align-items: center; justify-content: center; }
.rt-icon svg { display: block; width: 22px; height: 22px; }
/* The facts and the stats form one radio group: the chosen button keeps a lighter fill and a white
   icon, the other a dim icon. Steam's focus colours win over both. */
.rt-radio { display: flex; gap: 2px; }
.rt-actions .rt-radio .rt-act:not(.gpfocus) { color: var(--rt-dim) !important; }
.rt-actions .rt-radio .rt-act.rt-on:not(.gpfocus) { background: #67707b !important; color: #fff !important; }
.rt-stats { flex: 1; min-width: 0; display: flex; gap: 24px; margin: 0; overflow: hidden; }
.rt-stat { min-width: 0; max-width: 180px; }
.rt-stat dt { font-size: var(--rt-label); font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
  color: var(--rt-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rt-stat dd { margin: 0 0 0; font-size: var(--rt-body); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
/* An arcade game's page shows two lines of its history under the stats, then Game Info. Steam's
   buttons keep a 160px minimum width and their own padding. */
.rt-teaser { margin: 0; }
.rt-teaser p { margin: 0 0 12px; font-size: var(--rt-body); line-height: 1.45; display: -webkit-box;
  -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
.rt-teaser .rt-more { width: auto; min-width: 0; margin-top: 1.5em; padding: 8px 16px !important; font-size: var(--rt-body);
  letter-spacing: 0.5px; }
/* Game Info: a bar under Steam's status bar, then the capsule, the name and the whole history, and
   what the game plays with, in 3 columns. Each paragraph takes the focus, so that the D-pad scrolls
   through the text under the bar. The focused paragraph stops above Steam's footer. */
.rt-gameinfo { height: 100%; display: flex; flex-direction: column; }
.rt-infobar { flex: none; height: 40px; background: var(--rt-bar); border-bottom: 1px solid var(--rt-line); }
.rt-infobody { flex: 1; min-height: 0; overflow-y: auto; display: flex; align-items: flex-start; gap: 32px;
  padding: 24px 2.8vw 64px var(--rt-left); scroll-padding: 12px 0 56px; }
.rt-infocapsule { flex: none; width: 160px; aspect-ratio: 2 / 3; margin-top: 6px; background: var(--rt-card);
  box-shadow: 0 4px 10px #00000040; }
.rt-infocapsule img { display: block; width: 100%; height: 100%; object-fit: cover; }
.rt-history { flex: 1; min-width: 0; }
.rt-history h2 { margin: 0 0 12px; font-size: var(--rt-title); font-weight: 800; line-height: 1.15; color: #fff; }
.rt-infoside { flex: none; width: 220px; }
.rt-block { margin: 0 -12px; padding: 6px 12px; border-radius: 4px; }
.rt-block.rt-focus { background: #ffffff0f; }
.rt-block p { margin: 0; font-size: var(--rt-body); line-height: 1.45; white-space: pre-line; }
.rt-block h3 { margin: 18px 0 8px; font-size: var(--rt-heading); font-weight: 700; color: #fff; }
.rt-features { display: flex; flex-direction: column; gap: 14px; margin-top: 6px; }
.rt-feature { display: flex; align-items: center; gap: 14px; font-size: var(--rt-body); }
.rt-feature svg { flex: none; width: 24px; height: 24px; color: var(--rt-dim); }
.rt-infofacts { margin: 24px 0 0; display: flex; flex-direction: column; gap: 12px; }
.rt-infofacts dt { font-size: var(--rt-label); font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
  color: var(--rt-dim); }
.rt-infofacts dd { margin: 4px 0 0; font-size: var(--rt-body); }
.rt-credit { margin: 24px 0 0; font-size: var(--rt-meta); color: var(--rt-dim); }
/* Steam's tabs fill their parent, which needs a height in a dialog: 72vh keeps the dialog between
   the status bar and the footer. L1 and R1 switch the tabs without their glyphs. */
.rt-modal-tabs { position: relative; height: 72vh; }
.rt-modal .${gamepadTabbedPageClasses.Glyphs} { display: none; }
/* One file per line. */
.rt-files { margin: 12px 0 0; font-size: var(--rt-meta); color: var(--rt-dim); }
.rt-files > div { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rt-page .rt-files { margin: 0; }
.rt-prop-heading { margin: 32px 0 12px; font-size: var(--rt-body); font-weight: 700; }
.rt-prop-heading:first-child { margin-top: 0; }
/* A setting the game sets: its label, then the badge 12px after it on the label's baseline. */
.rt-setlabel { display: inline-flex; align-items: baseline; gap: 12px; }
.rt-setbadge { display: inline-block; padding: 4px; border-radius: 3px; background: var(--rt-ink); color: #0e141b;
  font-size: var(--rt-label); font-weight: 700; line-height: 1; text-transform: uppercase; letter-spacing: 0.04em;
  text-box: trim-both cap alphabetic; }
/* A note under a row, in the rows' type. */
.rt-prop-note { margin: 16px 12px; font-size: var(--rt-body); line-height: 1.5; color: var(--rt-ink); }
/* The libraries the scan found: the title, the list and the buttons on the left, the focused
   library in full on the right. The left title shares its baseline with the panel's. */
.rt-libs { height: 100%; display: flex; gap: 24px; padding: 0 2.8vw; box-sizing: border-box; }
.rt-libs-side { flex: none; width: 340px; display: flex; flex-direction: column; padding-top: 48px; }
.rt-libs-side h2 { margin: 0 0 24px; font-size: var(--rt-title); font-weight: 800; line-height: 1.15; color: #fff; }
.rt-libs-side p { margin: 0 0 20px; font-size: var(--rt-body); line-height: 1.45; color: var(--rt-dim); }
.rt-libs-list { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;
  padding-bottom: 56px; scroll-padding: 0 0 56px; }
/* A row: the drive's name in bold, its games or its role at the right. */
.rt-lib { flex: none; display: flex; align-items: baseline; gap: 12px; padding: 12px 16px; border-radius: 4px;
  background: var(--rt-card); }
.rt-lib.rt-focus { background: #3d4450; }
.rt-lib-name { min-width: 0; font-size: var(--rt-body); font-weight: 700; color: #fff; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.rt-lib-count { flex: none; margin-left: auto; font-size: var(--rt-body); }
.rt-libs-list .rt-new { flex: none; width: auto; text-align: left; }
/* Use All and Organize… share a row under the list. */
.rt-libs-actions { flex: none; display: flex; gap: 8px; margin-top: 24px; }
.rt-libs-actions .DialogButton { flex: 1; width: auto; min-width: 0; }
.rt-libs-side .rt-libs-note { margin: 12px 0 12px; }
.rt-libs-side .rt-libs-note.rt-libs-or { margin: 24px 0 12px; }
/* The panel keeps its height from one library to the next and stops above Steam's footer. The
   drive's icon sits left of the name. Everything else lines up with the name. */
.rt-detail { flex: 1; min-width: 0; box-sizing: border-box; margin: 24px 0 56px; padding: 24px 28px; overflow: hidden;
  display: grid; grid-template-columns: 40px 1fr; grid-template-rows: repeat(5, min-content) 1fr; column-gap: 16px;
  border-radius: 4px; background: var(--rt-card); }
/* The panel's text sits one step up the type scale: label and meta at 16px, body at 18px, heading at
   32px. */
.rt-detail { --rt-label: 16px; --rt-meta: 16px; --rt-body: 18px; --rt-heading: 32px; }
.rt-detail > :not(.rt-detail-drive) { grid-column: 2; }
/* The icon is centred on the name's line. Its negative margins keep the row as tall as the name. */
.rt-detail-drive { grid-row: 1; align-self: center; width: 40px; height: 40px; margin: -8px 0; color: var(--rt-dim); }
.rt-detail-drive svg { display: block; width: 100%; height: 100%; }
.rt-detail-name { display: flex; align-items: baseline; gap: 12px; font-size: var(--rt-heading); font-weight: 700;
  line-height: 1.15; color: #fff; }
.rt-detail-path { margin-top: 0px; font-size: var(--rt-meta); color: var(--rt-dim); overflow-wrap: anywhere; }
.rt-detail-stats { margin: 12px 0 28px; }
/* The rule separates the drive from its systems, from the text's left edge to the panel's right. */
.rt-detail-rule { height: 1px; margin-bottom: 20px; background: #ffffff3a; }
.rt-detail-systems { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 42px; }
.rt-system { display: flex; align-items: baseline; gap: 10px; font-size: var(--rt-body); }
.rt-system-name { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rt-system-count { margin-left: auto; color: var(--rt-dim); }
.rt-system-more { color: var(--rt-dim); }
/* A remark at the foot of the panel, 24px at least under the systems: Recommended, Tip or Note in the
   text's colour, then the advice. The panel's padding keeps it as far from the bottom as the name
   is from the top. */
.rt-detail > .rt-detail-note { grid-row: -2; align-self: end; margin: 24px 0 0; font-size: var(--rt-body); line-height: 1.45;
  color: var(--rt-dim); }
.rt-detail-note strong { color: var(--rt-ink); }
/* While the scan runs, the panel holds the lens. */
.rt-detail.rt-searching { display: flex; align-items: center; justify-content: center; }
.rt-lens { width: 60%; max-height: 80%; color: #ffffff12; }
${PANEL_CSS}`;
