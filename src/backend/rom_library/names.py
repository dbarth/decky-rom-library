"""Regions and languages from the letters in game ids and the tags of No-Intro and Redump file names."""
import re

# The region letter of N64, GameCube and Wii game ids.
REGION_LETTERS = {
    "A": "Asia", "B": "Brazil", "C": "China", "D": "Germany", "E": "USA", "F": "France", "H": "Netherlands",
    "I": "Italy", "J": "Japan", "K": "Korea", "N": "Canada", "P": "Europe", "R": "Russia", "S": "Spain",
    "U": "Australia", "W": "Taiwan", "X": "Europe", "Y": "Europe", "Z": "Europe",
}
REGIONS = {
    "World", "Europe", "USA", "Japan", "Asia", "Australia", "Brazil", "Canada", "China", "France", "Germany",
    "Hong Kong", "Italy", "Korea", "Netherlands", "Russia", "Scandinavia", "Spain", "Sweden", "Taiwan", "UK",
}
LANGUAGES = {
    "En": "English", "Fr": "French", "De": "German", "Es": "Spanish", "It": "Italian", "Nl": "Dutch",
    "Pt": "Portuguese", "Sv": "Swedish", "No": "Norwegian", "Da": "Danish", "Fi": "Finnish", "Ja": "Japanese",
    "Zh": "Chinese", "Ko": "Korean", "Ru": "Russian", "Pl": "Polish", "Ca": "Catalan", "El": "Greek",
}
TAG = re.compile(r"\(([^()]*)\)")


def from_file_name(name):
    """Return {region, languages} from the tags of a No-Intro or Redump name, each when present."""
    out = {}
    for tag in TAG.findall(name):
        parts = [p.strip() for p in tag.split(",")]
        if "region" not in out and all(p in REGIONS for p in parts):
            out["region"] = ", ".join(parts)
        elif "languages" not in out and all(p in LANGUAGES for p in parts):
            out["languages"] = [LANGUAGES[p] for p in parts]
    return out
