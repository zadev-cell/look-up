"""Turn angles, magnitudes and times into words people use when they look up."""

from __future__ import annotations

import re
from datetime import date, datetime

COMPASS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
COMPASS_SHORT = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# Words people type for a direction, mapped to an azimuth in degrees (0 = north, 90 = east).
_DIRECTIONS = {
    "n": 0,
    "north": 0,
    "nord": 0,
    "nne": 22.5,
    "north-northeast": 22.5,
    "ne": 45,
    "northeast": 45,
    "nord-est": 45,
    "nordest": 45,
    "ene": 67.5,
    "east-northeast": 67.5,
    "e": 90,
    "east": 90,
    "est": 90,
    "ese": 112.5,
    "east-southeast": 112.5,
    "se": 135,
    "southeast": 135,
    "sud-est": 135,
    "sudest": 135,
    "sse": 157.5,
    "south-southeast": 157.5,
    "s": 180,
    "south": 180,
    "sud": 180,
    "ssw": 202.5,
    "south-southwest": 202.5,
    "sw": 225,
    "southwest": 225,
    "sud-ouest": 225,
    "sudouest": 225,
    "wsw": 247.5,
    "west-southwest": 247.5,
    "w": 270,
    "west": 270,
    "ouest": 270,
    "o": 270,
    "wnw": 292.5,
    "west-northwest": 292.5,
    "nw": 315,
    "northwest": 315,
    "nord-ouest": 315,
    "nordouest": 315,
    "nnw": 337.5,
    "north-northwest": 337.5,
}

# Height words mapped to an altitude range in degrees.
_HEIGHTS = {
    "horizon": (0, 12),
    "very low": (0, 12),
    "on the horizon": (0, 10),
    "near the horizon": (0, 15),
    "low": (0, 25),
    "fairly low": (8, 30),
    "medium": (20, 55),
    "middle": (20, 55),
    "halfway": (25, 60),
    "halfway up": (25, 60),
    "mid": (20, 55),
    "high": (45, 85),
    "very high": (60, 90),
    "overhead": (70, 90),
    "straight up": (75, 90),
    "zenith": (75, 90),
}


def compass(az: float) -> str:
    """Eight-point compass word for an azimuth, e.g. 'southwest'."""
    return COMPASS[int(((az % 360) + 22.5) // 45) % 8]


def compass_short(az: float) -> str:
    return COMPASS_SHORT[int(((az % 360) + 22.5) // 45) % 8]


def direction_phrase(az: float) -> str:
    """'due south' when close to a cardinal point, otherwise 'in the southwest'."""
    az %= 360
    for center, name in ((0, "north"), (90, "east"), (180, "south"), (270, "west"), (360, "north")):
        if abs(az - center) <= 4:
            return f"due {name}"
    return f"in the {compass(az)}"


def fists(alt: float) -> str:
    """Altitude as fists at arm's length (one fist is about 10 degrees)."""
    if alt < 3:
        return "right on the horizon"
    halves = round(alt / 5)  # count in half-fists
    whole, half = divmod(halves, 2)
    if whole == 0:
        return "about half a fist up"
    label = f"{whole}½" if half else f"{whole}"
    return f"about {label} fist{'s' if halves > 2 else ''} up"


def height_word(alt: float) -> str:
    if alt < 0:
        return "below the horizon"
    if alt < 10:
        return "very low"
    if alt < 25:
        return "low"
    if alt < 50:
        return "halfway up"
    if alt < 75:
        return "high"
    return "nearly overhead"


def brightness(mag: float) -> str:
    if mag < -3:
        return "dazzling"
    if mag < -1:
        return "very bright"
    if mag < 0.6:
        return "bright"
    if mag < 2:
        return "easy to see"
    if mag < 3.5:
        return "visible from most places"
    if mag < 5:
        return "needs a dark sky"
    if mag < 6.5:
        return "needs binoculars"
    return "needs a telescope"


def clock(dt: datetime, base: date | None = None) -> str:
    """'21:17', or 'Mon 03:22' when the time falls on another day than base."""
    text = dt.strftime("%H:%M")
    if base is not None and dt.date() != base:
        text = f"{dt.strftime('%a')} {text}"
    return text


def day_label(d: date) -> str:
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b %Y')}"


def coords(lat: float, lon: float) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}°{ns}, {abs(lon):.2f}°{ew}"


def _clean(text: str) -> str:
    text = text.strip().lower().replace("–", "-").replace("—", "-").replace("_", " ")
    return re.sub(r"\s+", " ", text)


def _squash(text: str) -> str:
    return text.replace("-", "").replace(" ", "")


_DIRECTIONS_SQUASHED = {_squash(word): az for word, az in _DIRECTIONS.items()}


def _number(text: str) -> float | None:
    cleaned = text.removesuffix("°").removesuffix(" degrees").removesuffix(" deg").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_direction(text: str) -> float:
    """Azimuth in degrees from '225', 'SW', 'south west', 'south-west' or 'sud-ouest'.

    Raises ValueError with a hint when the text isn't a direction.
    """
    cleaned = _clean(text)
    value = _number(cleaned)
    if value is not None:
        return value % 360
    for prefix in ("the ", "towards ", "toward ", "to the "):
        cleaned = cleaned.removeprefix(prefix)
    squashed = _squash(cleaned)
    if squashed in _DIRECTIONS_SQUASHED:
        return float(_DIRECTIONS_SQUASHED[squashed])
    raise ValueError(
        f"'{text}' isn't a direction. Use a compass direction like 'SW' or 'south-west', "
        "or degrees from north (0 = north, 90 = east, 180 = south, 270 = west)."
    )


def parse_height(text: str) -> tuple[float, float]:
    """Altitude range in degrees from words like 'low' or 'overhead', or a number of degrees."""
    cleaned = _clean(text)
    value = _number(cleaned.removesuffix(" up").removesuffix(" high"))
    if value is not None:
        if not 0 <= value <= 90:
            raise ValueError("Height in degrees must be between 0 (horizon) and 90 (straight up).")
        return max(0.0, value - 10), min(90.0, value + 10)
    for candidate in (cleaned, cleaned.removesuffix(" up")):
        if candidate in _HEIGHTS:
            low, high = _HEIGHTS[candidate]
            return float(low), float(high)
    for word in sorted(_HEIGHTS, key=len, reverse=True):
        if word in cleaned:
            low, high = _HEIGHTS[word]
            return float(low), float(high)
    raise ValueError(
        f"'{text}' isn't a height. Use 'low', 'halfway', 'high' or 'overhead', or degrees above the horizon (0 to 90)."
    )
