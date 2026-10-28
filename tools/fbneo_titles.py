#!/usr/bin/env python3
"""Write src/backend/defaults/titles/fbneo.json from a FinalBurn Neo arcade DAT.

The file maps each set name to its title. BIOS sets map to null: the plugin
hides them, along with any set the DAT does not list.

Usage: tools/fbneo_titles.py DAT
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "backend" / "defaults" / "titles" / "fbneo.json"


def main():
    titles = {}
    for game in ET.parse(sys.argv[1]).getroot().iter("game"):
        bios = game.get("isbios") == "yes"
        titles[game.get("name")] = None if bios else game.findtext("description")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(titles, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"{len(titles)} sets, {sum(t is None for t in titles.values())} BIOS -> {OUT}")


if __name__ == "__main__":
    main()
