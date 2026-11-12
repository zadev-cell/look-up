"""Look Up: an MCP server that shows the night sky inside Claude.

Run it over HTTP with `look-up` (or `look-up stdio` for local clients).
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
from functools import cache
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastmcp import FastMCP
from fastmcp.apps import AppConfig
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__, sky, words
from .catalog import catalog, sky_data_json

VIEW_URI = "ui://look-up/sky.html"
APP_DIR = Path(__file__).parent / "app"
SDK_FILE = APP_DIR / "vendor" / "ext-apps-2.0.3.js"
NOTICES_FILE = Path(__file__).parent / "THIRD_PARTY_NOTICES.txt"

mcp = FastMCP(
    "Look Up",
    version=__version__,
    instructions=(
        "Look Up answers questions about the night sky for any place and time: what's visible tonight, "
        "where to find a planet, star, constellation or the Moon, what a bright light in the sky is, and "
        "when meteor showers peak. Pass the place's latitude, longitude and IANA time zone. Answers come "
        "with an interactive sky chart."
    ),
    mask_error_details=True,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
SKY_VIEW = AppConfig(resource_uri=VIEW_URI)

Latitude = Annotated[float, Field(ge=-90, le=90, description="Latitude of the place in degrees; north is positive.")]
Longitude = Annotated[
    float, Field(ge=-180, le=180, description="Longitude of the place in degrees; east is positive, west negative.")
]
TimeZone = Annotated[str, Field(description="IANA time zone of the place, like 'America/Toronto' or 'Europe/Paris'.")]
PlaceName = Annotated[str | None, Field(description="Name of the place to show on the chart, like 'Paris'.")]
LocalTime = Annotated[
    str | None,
    Field(description="Local date and time at the place, like '2026-11-08T21:30'. Leave out for right now."),
]


# ---------------------------------------------------------------- helpers


def _place(latitude: float, longitude: float, timezone: str, name: str | None) -> sky.Place:
    try:
        zone = ZoneInfo(timezone.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise ToolError(
            f"Unknown time zone '{timezone}'. Use an IANA name like 'America/Toronto', 'Europe/Paris' or 'Asia/Tokyo'."
        ) from None
    return sky.Place(latitude, longitude, zone, (name or "").strip() or None)


def _check_year(year: int) -> None:
    if not 1900 <= year <= 2100:
        raise ToolError("Dates must be between the years 1900 and 2100.")


def _when(text: str | None, place: sky.Place) -> dt.datetime:
    if not text:
        return dt.datetime.now(place.tz).replace(second=0, microsecond=0)
    try:
        when = dt.datetime.fromisoformat(text.strip())
    except ValueError:
        raise ToolError(
            f"'{text}' isn't a date and time. Use local time at the place, like '2026-11-08T21:30'."
        ) from None
    _check_year(when.year)
    return when.replace(tzinfo=place.tz) if when.tzinfo is None else when.astimezone(place.tz)


def _date(text: str | None, place_tz: ZoneInfo) -> dt.date | None:
    if not text:
        return None
    try:
        day = dt.date.fromisoformat(text.strip()[:10])
    except ValueError:
        raise ToolError(f"'{text}' isn't a date. Use the format YYYY-MM-DD, like '2026-12-14'.") from None
    _check_year(day.year)
    return day


def _result(report: sky.Report) -> ToolResult:
    return ToolResult(content=report.text, structured_content=report.payload)


# ---------------------------------------------------------------- tools


@mcp.tool(title="What's in the night sky", annotations=READ_ONLY, app=SKY_VIEW)
def sky_tonight(
    latitude: Latitude,
    longitude: Longitude,
    timezone: TimeZone,
    place: PlaceName = None,
    date: Annotated[
        str | None, Field(description="Local date of the evening, 'YYYY-MM-DD'. Leave out for tonight.")
    ] = None,
) -> ToolResult:
    """Shows what's in the night sky for a place and night: sunset and darkness times, the Moon's phase, which
    planets are visible and when, bright stars, and active meteor showers. Includes an interactive sky chart
    with a time slider."""
    where = _place(latitude, longitude, timezone, place)
    now = dt.datetime.now(where.tz)
    evening = _date(date, where.tz) or sky.evening_of(now)
    return _result(sky.sky_tonight(where, evening, now))


@mcp.tool(title="Find something in the sky", annotations=READ_ONLY, app=SKY_VIEW)
def find_object(
    name: Annotated[
        str,
        Field(
            description="What to find: a planet, the Moon or the Sun, a bright star, a constellation, or a famous "
            "sight like the Pleiades, Orion's Belt, the Big Dipper or the Andromeda Galaxy."
        ),
    ],
    latitude: Latitude,
    longitude: Longitude,
    timezone: TimeZone,
    place: PlaceName = None,
    time: LocalTime = None,
) -> ToolResult:
    """Finds a planet, the Moon, a star, a constellation or a famous sight from a place: where it is (compass
    direction and height), how bright it is, and when it rises, is highest and sets tonight. Includes an
    interactive sky chart pointed at it."""
    cat = catalog()
    if cat.is_satellite(name):
        raise ToolError(
            "Look Up doesn't track satellites or aircraft, only the Moon, planets, stars and constellations."
        )
    target = cat.resolve(name)
    if target is None:
        hints = cat.suggestions(name)
        hint = f" Did you mean {', '.join(hints)}?" if hints else ""
        raise ToolError(
            f"'{name}' isn't in Look Up's catalog.{hint} It knows the planets, the Moon and the Sun, about 480 "
            "named stars, the 88 constellations, and famous sights like the Pleiades or the Andromeda Galaxy."
        )
    where = _place(latitude, longitude, timezone, place)
    return _result(sky.find(target, where, _when(time, where)))


@mcp.tool(title="Identify a light in the sky", annotations=READ_ONLY, app=SKY_VIEW)
def identify_object(
    direction: Annotated[
        str,
        Field(
            description="Where the person is looking: a compass direction like 'SW' or 'south-west', or degrees "
            "from north (0 = north, 90 = east, 180 = south, 270 = west)."
        ),
    ],
    latitude: Latitude,
    longitude: Longitude,
    timezone: TimeZone,
    height: Annotated[
        str | None,
        Field(description="How high it is: 'low', 'halfway', 'high', 'overhead', or degrees above the horizon."),
    ] = None,
    place: PlaceName = None,
    time: LocalTime = None,
) -> ToolResult:
    """Identifies a bright light in the sky from the direction (and optionally the height) someone is looking:
    ranks the Moon, planets and bright stars there, brightest and closest first. Includes an interactive sky
    chart facing that way."""
    try:
        azimuth = words.parse_direction(direction)
        span = words.parse_height(height) if height else None
    except ValueError as error:
        raise ToolError(str(error)) from None
    where = _place(latitude, longitude, timezone, place)
    return _result(sky.identify(where, _when(time, where), azimuth, span))


@mcp.tool(title="Meteor showers", annotations=READ_ONLY)
def meteor_showers(
    date: Annotated[str | None, Field(description="Date to start from, 'YYYY-MM-DD'. Leave out for today.")] = None,
    latitude: Annotated[
        float | None,
        Field(ge=-90, le=90, description="Latitude of the viewer, to flag showers that are hard to see from there."),
    ] = None,
) -> ToolResult:
    """Lists meteor showers active now and the next ones coming up, with peak dates, how many meteors to
    expect, and how much moonlight will get in the way."""
    day = _date(date, ZoneInfo("UTC")) or dt.date.today()
    return ToolResult(content=sky.meteor_showers(day, latitude))


# ---------------------------------------------------------------- the sky view


_EXPORT_LIST = re.compile(r"export\s*\{([^}]*)\}\s*;?\s*$")


def sdk_as_global(source: str) -> str:
    """Turn the ext-apps ES module bundle into a script that sets globalThis.McpApps.

    The bundle ends with a single `export{a as App,...}` list; inlining it this way
    keeps the view one self-contained HTML file with no network access.
    """
    match = _EXPORT_LIST.search(source)
    if match is None:
        raise RuntimeError("The ext-apps bundle doesn't end with an export list; check the vendored file.")
    pairs = []
    for spec in match.group(1).split(","):
        local, _, exported = spec.strip().partition(" as ")
        if local:
            pairs.append(f"{(exported or local).strip()}:{local.strip()}")
    return source[: match.start()] + "globalThis.McpApps={" + ",".join(pairs) + "};"


def third_party_notices() -> str:
    text = NOTICES_FILE.read_text()
    if "-->" in text:
        raise RuntimeError("THIRD_PARTY_NOTICES.txt can't contain '-->' (it goes in an HTML comment).")
    return text


@cache
def _built_html() -> str:
    template = (APP_DIR / "sky.html").read_text()
    html = template.replace("/*__MCP_APPS_SDK__*/", sdk_as_global(SDK_FILE.read_text()))
    # Every copy of the view carries the licenses of the code and data inside it.
    html = html.replace("<!--__THIRD_PARTY_NOTICES__-->", f"<!--\n{third_party_notices()}\n-->")
    return html.replace("__SKY_DATA__", sky_data_json())


def app_html() -> str:
    """The sky view as one self-contained HTML file. LOOKUP_DEV=1 rebuilds it on every request."""
    if os.environ.get("LOOKUP_DEV") == "1":
        _built_html.cache_clear()
    return _built_html()


@mcp.resource(VIEW_URI, name="Sky view", description="Interactive sky chart used by Look Up's tools.")
def sky_view() -> str:
    return app_html()


# Landing, privacy and demo pages live in pages.py.
from . import pages  # noqa: E402

pages.register(mcp)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        mcp.run()
        return
    mcp.run(
        transport="http",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
