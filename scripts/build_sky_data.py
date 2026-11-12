"""Build src/look_up/data/sky.json from d3-celestial's data files.

d3-celestial (https://github.com/ofrohn/d3-celestial, BSD-3-Clause) ships stars
from the XHIP catalog and IAU constellation lines. We keep stars down to
magnitude 5.5, proper names and designations, and the 88 constellations with their
Latin and English names. Translations aren't kept: d3-celestial took them from
Stellarium (GPL) and Wikipedia (CC BY-SA).

Usage:
    uv run python scripts/build_sky_data.py <folder with the d3-celestial data files>

The folder needs stars.6.json, starnames.json, constellations.json and
constellations.lines.json from d3-celestial's data/ folder.
"""

import json
import sys
from pathlib import Path

MAG_LIMIT = 5.5
OUT = Path(__file__).resolve().parents[1] / "src" / "look_up" / "data" / "sky.json"
CREDIT = (
    "Derived from d3-celestial (BSD-3-Clause). Stars: the XHIP catalog via the VizieR catalogue access tool, "
    "CDS, Strasbourg, France. Constellation figures: adapted from the IAU constellation charts by the IAU and "
    "Sky & Telescope magazine, CC BY 4.0. See THIRD_PARTY_NOTICES.txt."
)


def ra_deg(lon: float, digits: int) -> float:
    """d3-celestial stores right ascension as longitude in -180..180 degrees."""
    return round(lon % 360, digits)


def build(src: Path) -> dict:
    stars = json.loads((src / "stars.6.json").read_text())["features"]
    names = json.loads((src / "starnames.json").read_text())
    constellations = json.loads((src / "constellations.json").read_text())["features"]
    lines = {
        f["id"]: f["geometry"]["coordinates"]
        for f in json.loads((src / "constellations.lines.json").read_text())["features"]
    }

    out_stars = []
    out_names = {}
    for feature in sorted(stars, key=lambda f: float(f["properties"]["mag"])):
        mag = float(feature["properties"]["mag"])
        if mag > MAG_LIMIT:
            continue
        lon, lat = feature["geometry"]["coordinates"]
        bv = feature["properties"].get("bv")
        bv = round(float(bv), 2) if bv not in (None, "") else None
        hip = int(feature["id"])
        out_stars.append([ra_deg(lon, 3), round(lat, 3), round(mag, 2), bv, hip])

        info = names.get(str(hip)) or {}
        if info.get("name"):
            letter = info.get("bayer") or info.get("flam") or ""
            desig = f"{letter} {info.get('c', '')}".strip() if letter else ""
            out_names[str(hip)] = [info["name"], desig]

    out_constellations = []
    for feature in constellations:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        segments = [[[ra_deg(x, 2), round(y, 2)] for x, y in segment] for segment in lines.get(feature["id"], [])]
        out_constellations.append(
            {
                "id": feature["id"],
                "name": props["name"],
                "en": props.get("en") or props["name"],
                "rank": int(props.get("rank") or 3),
                "label": [ra_deg(lon, 2), round(lat, 2)],
                "lines": segments,
            }
        )

    return {
        "credit": CREDIT,
        "stars": out_stars,
        "names": out_names,
        "constellations": out_constellations,
    }


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    data = build(Path(sys.argv[1]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(
        f"wrote {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}: "
        f"{len(data['stars'])} stars, {len(data['names'])} names, "
        f"{len(data['constellations'])} constellations, {OUT.stat().st_size // 1024} KB"
    )


if __name__ == "__main__":
    main()
