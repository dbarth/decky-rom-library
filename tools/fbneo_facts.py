#!/usr/bin/env python3
"""Write src/backend/defaults/facts/fbneo.json from FinalBurn Neo's driver sources, for the sets of
src/backend/defaults/titles/fbneo.json.

Each set maps to its year, manufacturer, board, players, genres, and flags for a game that does not
work or runs on a vertical screen. A clone names its parent.

Usage: tools/fbneo_facts.py FBNEO_SOURCE_TREE"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLES = ROOT / "src" / "backend" / "defaults" / "titles" / "fbneo.json"
OUT = ROOT / "src" / "backend" / "defaults" / "facts" / "fbneo.json"
DRIVER = re.compile(r"struct\s+BurnDriver[DX]?\s+\w+\s*=\s*\{(.*?)\};", re.S)
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
STRING = re.compile(r'L?"((?:[^"\\]|\\.)*)"')
# The genre bits of burn.h, in order from bit 0.
GENRES = [
    "Horizontal shooter", "Vertical shooter", "Beat 'em up", "Fighting", None, "Breakout", "Casino",
    "Ball and paddle", "Maze", "Mini-games", "Pinball", "Platform", "Puzzle", "Quiz", "Sports", "Football",
    None, "Mahjong", "Racing", "Shooter", "Multi-shooter", "Action", "Run and gun", "Strategy", None, "RPG",
    "Simulation", "Adventure", "Card", "Board",
]
BDF_GAME_WORKING = 1
BDF_ORIENTATION_VERTICAL = 4
BDF_BOOTLEG, BDF_PROTOTYPE, BDF_HACK, BDF_HOMEBREW, BDF_DEMO = 1 << 5, 1 << 6, 1 << 7, 1 << 8, 1 << 9


def fields(body):
    """Split a C initializer on the commas outside strings and parentheses."""
    out, depth, word, quote, i = [], 0, "", False, 0
    while i < len(body):
        c = body[i]
        if quote:
            word += c
            if c == "\\":
                word += body[i + 1]
                i += 1
            elif c == '"':
                quote = False
        elif c == '"':
            quote = True
            word += c
        elif c in "([{":
            depth += 1
            word += c
        elif c in ")]}":
            depth -= 1
            word += c
        elif c == "," and depth == 0:
            out.append(word.strip())
            word = ""
        else:
            word += c
        i += 1
    out.append(word.strip())
    return out


def string(field):
    found = STRING.findall(field)
    if not found:
        return None
    return "".join(found).replace("\\0", "\0").split("\0")[0].replace('\\"', '"').replace("\\\\", "\\").strip() or None


def bits(field, names):
    """Evaluate an expression of flag names joined by |, from #define values."""
    total = 0
    for token in re.split(r"\s*\|\s*", field.strip("() ")):
        if token.isdigit():
            total |= int(token)
        elif token.startswith("0x"):
            total |= int(token, 16)
        elif token in names:
            total |= names[token]
    return total


def defines(tree):
    """Return the flag values #define gives in FBNeo's headers: (1 << n) or a plain number."""
    names = {}
    for header in (tree / "src" / "burn").glob("*.h"):
        for m in re.finditer(r"#define\s+(\w+)\s+\(\s*(?:1\s*<<\s*(\d+)|(0x[0-9a-fA-F]+|\d+))\s*\)",
                             header.read_text(errors="replace")):
            names[m.group(1)] = 1 << int(m.group(2)) if m.group(2) else int(m.group(3), 0)
    return names


def main():
    tree = Path(sys.argv[1])
    names = defines(tree)
    wanted = json.loads(TITLES.read_text())
    out = {}
    for source in sorted((tree / "src" / "burn" / "drv").rglob("*.cpp")):
        for m in DRIVER.finditer(COMMENT.sub("", source.read_text(errors="replace"))):
            f = fields(m.group(1))
            short = string(f[0])
            if short not in wanted or wanted[short] is None or len(f) < 17:
                continue
            flags = bits(f[13], names)
            genre = bits(f[16], names)
            facts = {
                "year": string(f[4]),
                "maker": string(f[7]),
                "board": string(f[8]),
                "players": int(f[14]) if f[14].isdigit() else None,
                "genres": [g for i, g in enumerate(GENRES) if g and genre & (1 << i)],
                "parent": string(f[1]),
            }
            if not flags & BDF_GAME_WORKING:
                facts["broken"] = True
            if flags & BDF_ORIENTATION_VERTICAL:
                facts["vertical"] = True
            out[short] = {k: v for k, v in facts.items() if v not in (None, [], "Miscellaneous")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    missing = sorted(k for k, v in wanted.items() if v is not None and k not in out)
    print(f"{len(out)} sets -> {OUT}; {len(missing)} sets of the DAT not found: {missing[:10]}")


if __name__ == "__main__":
    main()
