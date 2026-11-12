"""Stars, constellations and famous sights, loaded from data/sky.json.

Positions are J2000 right ascension and declination in degrees.
"""

from __future__ import annotations

import difflib
import json
import math
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import astronomy as ae

DATA_FILE = Path(__file__).parent / "data" / "sky.json"

PLANETS = {
    "mercury": ae.Body.Mercury,
    "venus": ae.Body.Venus,
    "mars": ae.Body.Mars,
    "jupiter": ae.Body.Jupiter,
    "saturn": ae.Body.Saturn,
    "uranus": ae.Body.Uranus,
    "neptune": ae.Body.Neptune,
}
NAKED_EYE_PLANETS = ("mercury", "venus", "mars", "jupiter", "saturn")

_SOLAR_ALIASES = {
    "sun": "sun",
    "the sun": "sun",
    "soleil": "sun",
    "moon": "moon",
    "the moon": "moon",
    "lune": "moon",
    "la lune": "moon",
    "mercury": "mercury",
    "mercure": "mercury",
    "venus": "venus",
    "evening star": "venus",
    "morning star": "venus",
    "mars": "mars",
    "red planet": "mars",
    "jupiter": "jupiter",
    "saturn": "saturn",
    "saturne": "saturn",
    "uranus": "uranus",
    "neptune": "neptune",
}

_STAR_ALIASES = {
    "north star": "Polaris",
    "pole star": "Polaris",
    "polar star": "Polaris",
    "etoile polaire": "Polaris",
    "dog star": "Sirius",
    "alpha centauri": "Rigil Kentaurus",
    "alpha cen": "Rigil Kentaurus",
    "rigil kent": "Rigil Kentaurus",
}

_CONSTELLATION_ALIASES = {
    "little dipper": "UMi",
    "petite ourse": "UMi",
    "great bear": "UMa",
    "grande ourse": "UMa",
    "southern cross": "Cru",
    "crux": "Cru",
    "teapot": "Sgr",
    "the teapot": "Sgr",
    "the w": "Cas",
    "cassiopeia's w": "Cas",
    "northern cross": "Cyg",
    "the hunter": "Ori",
    "scorpion": "Sco",
    "serpens": "Ser1",
}

_SATELLITES = {
    "iss",
    "the iss",
    "space station",
    "international space station",
    "starlink",
    "starlink satellites",
    "satellite",
    "satellites",
    "hubble",
    "tiangong",
    "plane",
}


@dataclass(frozen=True)
class Star:
    hip: int
    ra: float
    dec: float
    mag: float
    bv: float | None
    name: str | None
    desig: str

    @property
    def id(self) -> str:
        return f"hip:{self.hip}"

    @property
    def label(self) -> str:
        return self.name or self.desig or f"HIP {self.hip}"


@dataclass(frozen=True)
class Target:
    """Something to find in the sky."""

    id: str
    name: str
    kind: str  # sun, moon, planet, star, constellation, asterism, cluster, nebula, galaxy, milky way
    body: ae.Body | None = None
    ra: float | None = None
    dec: float | None = None
    mag: float | None = None
    note: str = ""
    stars: tuple[Star, ...] = ()

    @property
    def is_fixed(self) -> bool:
        return self.body is None


# Famous sights that aren't single stars (J2000 positions).
_SIGHTS = [
    (
        "dso:m45",
        "the Pleiades",
        "cluster",
        56.75,
        24.12,
        1.6,
        "a tiny, misty dipper of stars",
        ("pleiades", "seven sisters", "m45", "subaru"),
    ),
    ("dso:hyades", "the Hyades", "cluster", 66.75, 15.87, 0.5, "a V of stars around Aldebaran", ("hyades",)),
    (
        "dso:m31",
        "the Andromeda Galaxy",
        "galaxy",
        10.68,
        41.27,
        3.4,
        "a faint oval smudge, needs a dark sky",
        ("andromeda galaxy", "m31", "andromeda nebula", "galaxie d'andromede"),
    ),
    (
        "dso:m42",
        "the Orion Nebula",
        "nebula",
        83.82,
        -5.39,
        4.0,
        "a fuzzy patch in Orion's sword",
        ("orion nebula", "m42", "great orion nebula"),
    ),
    (
        "dso:m44",
        "the Beehive Cluster",
        "cluster",
        130.10,
        19.98,
        3.7,
        "a faint grainy cloud, lovely in binoculars",
        ("beehive", "beehive cluster", "praesepe", "m44"),
    ),
    (
        "dso:m13",
        "the Hercules Cluster",
        "cluster",
        250.42,
        36.46,
        5.8,
        "a faint fuzzy ball, binoculars help",
        ("hercules cluster", "great hercules cluster", "m13"),
    ),
    (
        "dso:double-cluster",
        "the Double Cluster",
        "cluster",
        35.10,
        57.14,
        3.7,
        "two star clusters side by side",
        ("double cluster", "ngc 869", "ngc 884", "h and chi persei"),
    ),
    (
        "dso:galactic-center",
        "the core of the Milky Way",
        "milky way",
        266.42,
        -29.01,
        None,
        "the brightest part of the Milky Way, needs a dark sky",
        ("milky way", "the milky way", "milky way core", "galactic center", "galactic centre", "voie lactee"),
    ),
    (
        "dso:lmc",
        "the Large Magellanic Cloud",
        "galaxy",
        80.89,
        -69.76,
        0.9,
        "a big misty patch, a neighbor galaxy",
        ("large magellanic cloud", "lmc"),
    ),
    (
        "dso:smc",
        "the Small Magellanic Cloud",
        "galaxy",
        13.19,
        -72.83,
        2.7,
        "a smaller misty patch",
        ("small magellanic cloud", "smc"),
    ),
    (
        "dso:omega-centauri",
        "Omega Centauri",
        "cluster",
        201.70,
        -47.48,
        3.9,
        "a fuzzy star, really a ball of stars",
        ("omega centauri", "omega cen", "ngc 5139"),
    ),
    (
        "dso:m7",
        "the Ptolemy Cluster",
        "cluster",
        268.46,
        -34.79,
        3.3,
        "a bright cluster near the Scorpion's tail",
        ("ptolemy cluster", "m7"),
    ),
    (
        "dso:m8",
        "the Lagoon Nebula",
        "nebula",
        270.90,
        -24.39,
        6.0,
        "a faint glow in the Milky Way",
        ("lagoon nebula", "m8"),
    ),
    (
        "dso:carina-nebula",
        "the Carina Nebula",
        "nebula",
        161.26,
        -59.87,
        1.0,
        "a glowing cloud in the southern Milky Way",
        ("carina nebula", "eta carinae nebula", "ngc 3372"),
    ),
    (
        "dso:47-tuc",
        "47 Tucanae",
        "cluster",
        6.02,
        -72.08,
        4.1,
        "a fuzzy star next to the Small Magellanic Cloud",
        ("47 tucanae", "47 tuc", "ngc 104"),
    ),
]

# Star patterns, by member star names (or HIP numbers when a name is ambiguous).
_ASTERISMS = [
    (
        "ast:big-dipper",
        "the Big Dipper",
        "seven stars shaped like a ladle",
        ("big dipper", "plough", "the plough", "plow", "the plow", "grande casserole"),
        ("Dubhe", "Merak", "Phecda", "Megrez", "Alioth", "Mizar", "Alkaid"),
    ),
    (
        "ast:summer-triangle",
        "the Summer Triangle",
        "three bright stars in a big triangle",
        ("summer triangle",),
        ("Vega", "Deneb", "Altair"),
    ),
    (
        "ast:winter-triangle",
        "the Winter Triangle",
        "three bright stars in a big triangle",
        ("winter triangle",),
        ("Betelgeuse", "Sirius", "Procyon"),
    ),
    (
        "ast:orions-belt",
        "Orion's Belt",
        "three stars in a short straight row",
        ("orion's belt", "orions belt", "belt of orion", "three kings"),
        ("Alnitak", "Alnilam", "Mintaka"),
    ),
    (
        "ast:great-square",
        "the Great Square of Pegasus",
        "four stars in a big square",
        ("great square", "great square of pegasus", "square of pegasus"),
        (113963, 113881, 1067, 677),
    ),
]


def _key(text: str) -> str:
    """Lowercase, strip accents and extra spaces."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().replace("’", "'").split())


def _unit(ra: float, dec: float) -> tuple[float, float, float]:
    r, d = math.radians(ra), math.radians(dec)
    return (math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d))


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    x = y = z = 0.0
    for ra, dec in points:
        ux, uy, uz = _unit(ra, dec)
        x, y, z = x + ux, y + uy, z + uz
    ra = math.degrees(math.atan2(y, x)) % 360
    dec = math.degrees(math.atan2(z, math.hypot(x, y)))
    return ra, dec


class Catalog:
    def __init__(self, data: dict):
        self.credit: str = data["credit"]
        names = data["names"]
        self.stars: list[Star] = []
        for ra, dec, mag, bv, hip in data["stars"]:
            name, desig = names.get(str(hip), (None, ""))
            self.stars.append(Star(hip, ra, dec, mag, bv, name, desig))
        self.by_hip = {s.hip: s for s in self.stars}

        # Names: when two stars share a name, keep the Bayer alpha, then the brighter one.
        self.by_name: dict[str, Star] = {}
        for star in sorted(self.stars, key=lambda s: (not s.desig.startswith("α"), s.mag)):
            if star.name:
                self.by_name.setdefault(_key(star.name), star)

        self.constellations: dict[str, Target] = {}
        self._constellation_keys: dict[str, str] = {}
        stars_at = {(round(s.ra, 1), round(s.dec, 1)): s for s in self.stars}
        for c in data["constellations"]:
            vertices = [(ra, dec) for segment in c["lines"] for ra, dec in segment]
            members = {
                stars_at[(round(ra, 1), round(dec, 1))]
                for ra, dec in vertices
                if (round(ra, 1), round(dec, 1)) in stars_at
            }
            ra, dec = _centroid(vertices) if vertices else tuple(c["label"])
            target = Target(
                id=f"con:{c['id']}",
                name=c["name"],
                kind="constellation",
                ra=ra,
                dec=dec,
                note=f"the {c['en']}" if c["en"] != c["name"] else "",
                stars=tuple(sorted(members, key=lambda s: s.mag)[:3]),
            )
            self.constellations[c["id"]] = target
            for alias in (c["id"], c["name"], c["en"]):
                self._constellation_keys.setdefault(_key(alias), c["id"])
        for alias, cid in _CONSTELLATION_ALIASES.items():
            self._constellation_keys[_key(alias)] = cid

        self.sights: dict[str, Target] = {}
        self._sight_keys: dict[str, str] = {}
        for sid, name, kind, ra, dec, mag, note, aliases in _SIGHTS:
            self.sights[sid] = Target(id=sid, name=name, kind=kind, ra=ra, dec=dec, mag=mag, note=note)
            for alias in (name, name.removeprefix("the "), *aliases):
                self._sight_keys[_key(alias)] = sid
        for sid, name, note, aliases, members in _ASTERISMS:
            stars = tuple(self.by_hip[m] if isinstance(m, int) else self.by_name[_key(m)] for m in members)
            ra, dec = _centroid([(s.ra, s.dec) for s in stars])
            self.sights[sid] = Target(
                id=sid,
                name=name,
                kind="asterism",
                ra=ra,
                dec=dec,
                mag=min(s.mag for s in stars),
                note=note,
                stars=stars,
            )
            for alias in (name, name.removeprefix("the "), *aliases):
                self._sight_keys[_key(alias)] = sid

    def star_target(self, star: Star) -> Target:
        return Target(id=star.id, name=star.label, kind="star", ra=star.ra, dec=star.dec, mag=star.mag, stars=(star,))

    def planet_target(self, key: str) -> Target:
        if key == "sun":
            return Target(id="sun", name="the Sun", kind="sun", body=ae.Body.Sun, mag=-26.7)
        if key == "moon":
            return Target(id="moon", name="the Moon", kind="moon", body=ae.Body.Moon)
        return Target(id=key, name=key.capitalize(), kind="planet", body=PLANETS[key])

    def resolve(self, query: str) -> Target | None:
        """Find a target by name. Returns None when nothing matches."""
        k = _key(query)
        if k in _SOLAR_ALIASES:
            return self.planet_target(_SOLAR_ALIASES[k])
        if k in _STAR_ALIASES:
            return self.star_target(self.by_name[_key(_STAR_ALIASES[k])])
        if k in self._sight_keys:
            return self.sights[self._sight_keys[k]]
        if k in self.by_name:
            return self.star_target(self.by_name[k])
        if k in self._constellation_keys:
            return self.constellations[self._constellation_keys[k]]
        bare = k.removeprefix("the ").removeprefix("constellation ").removesuffix(" constellation")
        if bare != k:
            return self.resolve(bare)
        return None

    def is_satellite(self, query: str) -> bool:
        return _key(query) in _SATELLITES

    def suggestions(self, query: str, limit: int = 3) -> list[str]:
        names = list(_SOLAR_ALIASES) + list(self.by_name) + list(self._sight_keys) + list(self._constellation_keys)
        matches = difflib.get_close_matches(_key(query), names, n=limit * 3, cutoff=0.7)
        out: list[str] = []
        for match in matches:
            target = self.resolve(match)
            if target and target.name not in out:
                out.append(target.name)
        return out[:limit]

    def bright_named_stars(self, max_mag: float) -> list[Star]:
        return [s for s in self.stars if s.name and s.mag <= max_mag]


@cache
def catalog() -> Catalog:
    return Catalog(json.loads(DATA_FILE.read_text()))


def sky_data_json() -> str:
    """The raw data file, embedded in the sky view."""
    return DATA_FILE.read_text()
