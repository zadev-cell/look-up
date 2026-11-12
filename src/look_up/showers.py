"""Major annual meteor showers.

Dates follow the International Meteor Organization's calendar. Peaks move by a
day or so from year to year, so they're given as "around".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

import astronomy as ae


@dataclass(frozen=True)
class Shower:
    name: str
    start: tuple[int, int]  # (month, day) activity begins
    peak: tuple[int, int]
    end: tuple[int, int]
    rate: int  # meteors per hour at the peak under a perfect dark sky (ZHR)
    radiant_ra: float  # degrees
    radiant_dec: float
    note: str


SHOWERS = [
    Shower("Quadrantids", (12, 28), (1, 3), (1, 12), 110, 230.0, 49.0, "a short, sharp peak of a few hours"),
    Shower("Lyrids", (4, 14), (4, 22), (4, 30), 18, 271.0, 34.0, "occasional bright meteors"),
    Shower("Eta Aquariids", (4, 19), (5, 6), (5, 28), 50, 338.0, -1.0, "best before dawn, from the tropics and south"),
    Shower("Southern Delta Aquariids", (7, 12), (7, 30), (8, 23), 25, 340.0, -16.0, "best from the south"),
    Shower("Perseids", (7, 17), (8, 12), (8, 24), 100, 48.0, 58.0, "fast and bright, the summer favorite"),
    Shower("Draconids", (10, 6), (10, 8), (10, 10), 10, 262.0, 54.0, "best in the evening; usually weak"),
    Shower("Orionids", (10, 2), (10, 21), (11, 7), 20, 95.0, 16.0, "fast meteors from Halley's Comet"),
    Shower("Southern Taurids", (9, 10), (10, 10), (11, 20), 5, 32.0, 9.0, "slow, sometimes bright fireballs"),
    Shower("Northern Taurids", (10, 20), (11, 12), (12, 10), 5, 58.0, 22.0, "slow, sometimes bright fireballs"),
    Shower("Leonids", (11, 6), (11, 17), (11, 30), 15, 152.0, 22.0, "very fast meteors, best before dawn"),
    Shower("Geminids", (12, 4), (12, 14), (12, 20), 150, 112.0, 33.0, "the year's richest shower, good all night"),
    Shower("Ursids", (12, 17), (12, 22), (12, 26), 10, 217.0, 76.0, "best from the north"),
]


def _on(year: int, month_day: tuple[int, int]) -> date:
    return date(year, *month_day)


def _window(shower: Shower, year: int) -> tuple[date, date, date]:
    """Activity window and peak for the occurrence that peaks in `year`."""
    peak = _on(year, shower.peak)
    start = _on(year, shower.start)
    end = _on(year, shower.end)
    if start > peak:  # starts the year before (Quadrantids)
        start = _on(year - 1, shower.start)
    if end < peak:
        end = _on(year + 1, shower.end)
    return start, peak, end


def active_on(day: date) -> list[tuple[Shower, date]]:
    """Showers active on a date, with their peak date."""
    out = []
    for shower in SHOWERS:
        for year in (day.year - 1, day.year, day.year + 1):
            start, peak, end = _window(shower, year)
            if start <= day <= end:
                out.append((shower, peak))
    return out


def upcoming(day: date, count: int = 3) -> list[tuple[Shower, date]]:
    """The next `count` shower peaks on or after `day`."""
    peaks = []
    for shower in SHOWERS:
        for year in (day.year, day.year + 1):
            peak = _on(year, shower.peak)
            if peak >= day:
                peaks.append((peak, shower))
                break
    peaks.sort(key=lambda p: p[0])
    return [(shower, peak) for peak, shower in peaks[:count]]


def moon_lit_at_peak(peak: date) -> float:
    """Fraction of the Moon lit around the peak night (0 to 1)."""
    when = datetime.combine(peak, time(6, 0), UTC)
    t = ae.Time.Make(when.year, when.month, when.day, when.hour, 0, 0)
    return ae.Illumination(ae.Body.Moon, t).phase_fraction


def radiant_height(shower: Shower, latitude: float) -> float:
    """Highest the radiant gets above the horizon from a latitude, in degrees."""
    return 90 - abs(latitude - shower.radiant_dec)


def describe(shower: Shower, peak: date, latitude: float | None = None, today: date | None = None) -> str:
    lit = moon_lit_at_peak(peak)
    if lit < 0.25:
        moon = "little moonlight"
    elif lit < 0.6:
        moon = f"Moon {round(lit * 100)}% lit"
    else:
        moon = f"bright Moon ({round(lit * 100)}% lit) will hide fainter meteors"
    when = f"{peak.strftime('%a')} {peak.day} {peak.strftime('%b')}"
    if today is not None and peak < today:
        timing = f"peaked around {when} and is winding down"
    else:
        timing = f"peak around {when}"
    text = f"{shower.name}: {timing}, up to about {shower.rate} per hour under a dark sky, {shower.note}; {moon}."
    if latitude is not None and radiant_height(shower, latitude) < 15:
        text += " Hard to see from your latitude (the radiant stays low)."
    return text
