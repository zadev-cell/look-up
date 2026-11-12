"""What's in the sky: positions, the night's timeline, and plain-language reports.

Every report returns two things: text for the model, and a payload for the sky
view (see `view_payload`). Times in the text are local to the place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import astronomy as ae

from . import showers, words
from .catalog import NAKED_EYE_PLANETS, PLANETS, Star, Target, catalog

UTC = UTC
REFRACTION = ae.Refraction.Normal
STEP = timedelta(minutes=10)
PHASES = ["new moon", "first quarter", "full moon", "last quarter"]
SHOWPIECES = (
    "dso:m45",
    "dso:m31",
    "dso:m42",
    "dso:galactic-center",
    "dso:lmc",
    "dso:omega-centauri",
    "dso:double-cluster",
    "dso:m44",
)


@dataclass(frozen=True)
class Place:
    lat: float
    lon: float
    tz: ZoneInfo
    name: str | None = None

    @property
    def observer(self) -> ae.Observer:
        return ae.Observer(self.lat, self.lon, 0.0)

    @property
    def label(self) -> str:
        return self.name or words.coords(self.lat, self.lon)


@dataclass(frozen=True)
class Sample:
    when: datetime
    alt: float
    az: float


@dataclass(frozen=True)
class Night:
    evening: date
    sunset: datetime | None
    dusk: datetime | None  # fully dark: the Sun is 18° below the horizon
    dawn: datetime | None
    sunrise: datetime | None
    start: datetime  # the view's time range
    end: datetime
    polar: str | None  # "day" or "night" when the Sun doesn't set or doesn't rise


@dataclass(frozen=True)
class Pass:
    """An object's path across one night."""

    samples: list[Sample]
    visible: list[Sample]  # above the horizon while the sky is dark enough to see it
    rise: Sample | None
    set: Sample | None
    peak: Sample
    up_at_dark: bool  # already up when the sky got dark enough


# ---------------------------------------------------------------- time helpers


def atime(dt: datetime) -> ae.Time:
    u = dt.astimezone(UTC)
    return ae.Time.Make(u.year, u.month, u.day, u.hour, u.minute, u.second + u.microsecond / 1e6)


def local(t: ae.Time, tz: ZoneInfo) -> datetime:
    return t.Utc().replace(tzinfo=UTC).astimezone(tz)


def epoch_ms(dt: datetime) -> int:
    return round(dt.timestamp() * 1000)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


# ---------------------------------------------------------------- positions


def altaz(target: Target, when: datetime, place: Place) -> tuple[float, float]:
    """Apparent altitude and compass azimuth in degrees, with refraction."""
    t = atime(when)
    if target.body is not None:
        eq = ae.Equator(target.body, t, place.observer, True, True)
        hor = ae.Horizon(t, place.observer, eq.ra, eq.dec, REFRACTION)
        return hor.altitude, hor.azimuth
    return fixed_altaz(target.ra, target.dec, t, ae.Rotation_EQJ_HOR(t, place.observer))


def fixed_altaz(ra: float, dec: float, t: ae.Time, rot: ae.RotationMatrix) -> tuple[float, float]:
    vec = ae.VectorFromSphere(ae.Spherical(dec, ra, 1.0), t)
    sph = ae.HorizonFromVector(ae.RotateVector(rot, vec), REFRACTION)
    return sph.lat, sph.lon


def magnitude(target: Target, when: datetime) -> float | None:
    if target.kind in ("planet", "moon"):
        return ae.Illumination(target.body, atime(when)).mag
    return target.mag


def constellation_of(target: Target, when: datetime, place: Place) -> str | None:
    if target.kind in ("constellation", "asterism", "sun", "milky way"):
        return None
    if target.body is not None:
        eq = ae.Equator(target.body, atime(when), place.observer, False, True)
        return ae.Constellation(eq.ra, eq.dec).name
    return ae.Constellation(target.ra / 15, target.dec).name


def sun_altitude(when: datetime, place: Place) -> float:
    return altaz(catalog().planet_target("sun"), when, place)[0]


def dark_enough(sun_alt: float, mag: float) -> bool:
    """Whether an object of this magnitude shows up with the Sun at this altitude."""
    if mag <= -1.5:
        return sun_alt <= -3
    if mag <= 0.5:
        return sun_alt <= -6
    if mag <= 2.0:
        return sun_alt <= -9
    if mag <= 4.0:
        return sun_alt <= -12
    return sun_alt <= -15


# ---------------------------------------------------------------- the night


def night_of(evening: date, place: Place) -> Night:
    """Sunset to sunrise for the night that starts on `evening` (a local date)."""
    tz, obs = place.tz, place.observer
    noon = datetime.combine(evening, time(12), tz)
    t0 = atime(noon)

    def when(t: ae.Time | None) -> datetime | None:
        return local(t, tz) if t is not None else None

    sunset = when(ae.SearchRiseSet(ae.Body.Sun, obs, ae.Direction.Set, t0, 1.0))
    sunrise = when(ae.SearchRiseSet(ae.Body.Sun, obs, ae.Direction.Rise, t0, 1.0))
    dusk = when(ae.SearchAltitude(ae.Body.Sun, obs, ae.Direction.Set, t0, 1.0, -18))
    dawn = when(ae.SearchAltitude(ae.Body.Sun, obs, ae.Direction.Rise, t0, 1.0, -18))

    polar = None
    if sunset is None and sunrise is None:
        polar = "day" if sun_altitude(noon, place) > 0 else "night"

    start = sunset - timedelta(minutes=30) if sunset else datetime.combine(evening, time(17), tz)
    end = sunrise + timedelta(minutes=30) if sunrise and sunrise > start else start + timedelta(hours=14)
    end = min(end, start + timedelta(hours=20))
    return Night(evening, sunset, dusk, dawn, sunrise, start, end, polar)


def evening_of(when: datetime) -> date:
    """The evening a moment belongs to: 02:00 on the 9th is the night of the 8th."""
    return (when - timedelta(hours=12)).date()


def default_view_time(n: Night, place: Place, now: datetime) -> datetime:
    """Now if it's dark, otherwise a typical stargazing time (20:30, or later if it gets dark late)."""
    if n.start <= now <= n.end:
        midpoint = n.start + (n.end - n.start) / 2
        if now > midpoint or sun_altitude(now, place) < -8:
            return now.replace(second=0, microsecond=0)
    base = n.sunset + timedelta(minutes=105) if n.sunset else n.start + timedelta(hours=3)
    evening = datetime.combine(n.evening, time(20, 30), place.tz)
    return min(max(base, evening), n.end - timedelta(minutes=30))


def track(target: Target, start: datetime, end: datetime, place: Place) -> list[Sample]:
    out = []
    when = start
    while when <= end:
        alt, az = altaz(target, when, place)
        out.append(Sample(when, alt, az))
        when += STEP
    return out


def _crossing(a: Sample, b: Sample) -> Sample:
    """Where the path between two samples crosses the horizon."""
    f = a.alt / (a.alt - b.alt)
    when = a.when + (b.when - a.when) * f
    daz = ((b.az - a.az + 180) % 360) - 180
    return Sample(when, 0.0, (a.az + daz * f) % 360)


def _refine_peak(samples: list[Sample], i: int) -> Sample:
    """Fit a parabola through the highest sample and its neighbors."""
    if i == 0 or i == len(samples) - 1:
        return samples[i]
    a0, a1, a2 = samples[i - 1].alt, samples[i].alt, samples[i + 1].alt
    denom = a0 - 2 * a1 + a2
    if denom >= 0:
        return samples[i]
    shift = 0.5 * (a0 - a2) / denom
    alt = a1 - 0.25 * (a0 - a2) * shift
    return Sample(samples[i].when + STEP * shift, alt, samples[i].az)


def night_pass(target: Target, n: Night, place: Place, sun: list[Sample], mag: float, min_alt: float = 5) -> Pass:
    samples = track(target, n.start, n.end, place)
    visible = [s for s, z in zip(samples, sun, strict=True) if s.alt >= min_alt and dark_enough(z.alt, mag)]
    rise = set_ = None
    for a, b in zip(samples, samples[1:], strict=False):
        if rise is None and a.alt < 0 <= b.alt:
            rise = _crossing(a, b)
        if set_ is None and a.alt >= 0 > b.alt:
            set_ = _crossing(a, b)
    peak_i = max(range(len(samples)), key=lambda i: samples[i].alt)
    dark_start = next((s.when for s, z in zip(samples, sun, strict=True) if dark_enough(z.alt, mag)), None)
    up_at_dark = bool(visible) and dark_start is not None and visible[0].when <= dark_start
    return Pass(samples, visible, rise, set_, _refine_peak(samples, peak_i), up_at_dark)


def best_of(p: Pass) -> Sample | None:
    """Highest point while visible."""
    if not p.visible:
        return None
    best = max(p.visible, key=lambda s: s.alt)
    if abs(best.alt - p.peak.alt) < 0.5 and abs((best.when - p.peak.when).total_seconds()) <= 600:
        return p.peak
    return best


def describe_pass(p: Pass, base: date) -> str:
    """'up as it gets dark low in the southeast, highest at 21:17 (46° up, due south), sets 03:22 in the west'"""
    first, last, best = p.visible[0], p.visible[-1], best_of(p)
    parts = []
    if p.up_at_dark:
        parts.append(f"up as it gets dark, {words.height_word(first.alt)} in the {words.compass(first.az)}")
    elif p.rise and p.rise.when <= first.when:
        parts.append(f"rises {words.clock(p.rise.when, base)} in the {words.compass(p.rise.az)}")
    else:
        parts.append(f"appears {words.clock(first.when, base)} in the {words.compass(first.az)}")
    if best is not None:
        label = "highest at" if best is p.peak else "best around"
        parts.append(
            f"{label} {words.clock(best.when, base)} ({round(best.alt)}° up, {words.direction_phrase(best.az)})"
        )
    if p.set and p.set.when >= last.when - STEP * 2:
        parts.append(f"sets {words.clock(p.set.when, base)} in the {words.compass(p.set.az)}")
    else:
        parts.append(f"still up at dawn in the {words.compass(last.az)}")
    return ", ".join(parts)


# ---------------------------------------------------------------- the view payload


def view_payload(
    *,
    view: str,
    place: Place,
    n: Night,
    when: datetime,
    facing: float,
    focus_alt: float | None = None,
    highlight: list[str] | None = None,
    markers: list[Target] | None = None,
    notes: dict[str, str] | None = None,
) -> dict:
    """Data for the interactive sky view.

    Solar system bodies come as hourly J2000 positions seen from the place; the view
    applies `precession` and sidereal time to put them, and the stars, on the sky.
    """
    obs = place.observer
    times = []
    t = n.start
    while t < n.end:
        times.append(t)
        t += timedelta(hours=1)
    times.append(n.end)

    cat = catalog()
    bodies = []
    for key in ("sun", "moon", *PLANETS):
        target = cat.planet_target(key)
        samples = []
        for dt in times:
            eq = ae.Equator(target.body, atime(dt), obs, False, True)
            samples.append([epoch_ms(dt), round(eq.ra * 15, 4), round(eq.dec, 4)])
        entry = {"id": target.id, "name": target.name.removeprefix("the "), "kind": target.kind, "samples": samples}
        if key == "moon":
            entry["lit"] = round(ae.Illumination(ae.Body.Moon, atime(when)).phase_fraction, 3)
        if target.kind == "planet":
            entry["mag"] = round(magnitude(target, when), 2)
        bodies.append(entry)

    t_start = atime(n.start)
    events = [
        {"kind": kind, "time": iso(dt)}
        for kind, dt in (("sunset", n.sunset), ("dusk", n.dusk), ("dawn", n.dawn), ("sunrise", n.sunrise))
        if dt is not None and n.start <= dt <= n.end
    ]
    return {
        "view": view,
        "place": {"name": place.label, "lat": place.lat, "lon": place.lon, "tz": place.tz.key},
        "time": iso(when),
        "range": [iso(n.start), iso(n.end)],
        "events": events,
        "facing": round(facing % 360, 1),
        "focusAlt": None if focus_alt is None else round(focus_alt, 1),
        "highlight": highlight or [],
        "markers": [
            {
                "id": m.id,
                "name": m.name.removeprefix("the "),
                "kind": m.kind,
                "ra": round(m.ra, 3),
                "dec": round(m.dec, 3),
                "stars": [s.id for s in m.stars],
            }
            for m in (markers or [])
        ],
        "bodies": bodies,
        "lst0": round((ae.SiderealTime(t_start) * 15 + place.lon) % 360, 5),
        "t0": epoch_ms(n.start),
        "precession": [[round(v, 9) for v in row] for row in ae.Rotation_EQJ_EQD(atime(when)).rot],
        "notes": notes or {},
    }


# ---------------------------------------------------------------- moon


def moon_phase_name(angle: float) -> str:
    if angle < 6 or angle > 354:
        return "new moon"
    if angle < 84:
        return "waxing crescent"
    if angle < 96:
        return "first quarter"
    if angle < 174:
        return "waxing gibbous"
    if angle < 186:
        return "full moon"
    if angle < 264:
        return "waning gibbous"
    if angle < 276:
        return "last quarter"
    return "waning crescent"


def moon_summary(n: Night, place: Place, sun: list[Sample], when: datetime) -> tuple[str, float]:
    """One line about the Moon tonight, and the fraction lit."""
    t = atime(when)
    angle = ae.MoonPhase(t)
    lit = ae.Illumination(ae.Body.Moon, t).phase_fraction
    pct = round(lit * 100)
    quarter = ae.SearchMoonQuarter(t)
    if PHASES[quarter.quarter] == moon_phase_name(angle):  # we're in that phase now; name the one after
        quarter = ae.SearchMoonQuarter(quarter.time.AddDays(1))
    quarter_at = local(quarter.time, place.tz)
    next_phase = (
        f"{PHASES[quarter.quarter]} on {quarter_at.strftime('%a')} {quarter_at.day} {quarter_at.strftime('%b')}"
    )

    moon = catalog().planet_target("moon")
    samples = track(moon, n.start, n.end, place)
    dark = [s for s, z in zip(samples, sun, strict=True) if z.alt <= -6]
    up = [s for s in dark if s.alt > 2]
    name = moon_phase_name(angle)

    if lit < 0.03:
        return f"Moon: {name} ({pct}% lit), not in the sky tonight, so it's a dark night. Next: {next_phase}.", lit
    if not dark:
        return f"Moon: {name}, {pct}% lit. The sky doesn't get dark tonight. Next: {next_phase}.", lit
    if not up:
        return f"Moon: {name}, {pct}% lit, below the horizon while it's dark. Next: {next_phase}.", lit
    obs = place.observer
    rise = ae.SearchRiseSet(
        ae.Body.Moon, obs, ae.Direction.Rise, atime(n.start), (n.end - n.start).total_seconds() / 86400
    )
    sett = ae.SearchRiseSet(
        ae.Body.Moon, obs, ae.Direction.Set, atime(n.start), (n.end - n.start).total_seconds() / 86400
    )
    bits = []
    if up[0].when == dark[0].when:
        bits.append(f"up as it gets dark in the {words.compass(up[0].az)}")
    elif rise is not None:
        rise_at = local(rise, place.tz)
        bits.append(f"rises {words.clock(rise_at, n.evening)} in the {words.compass(altaz(moon, rise_at, place)[1])}")
    if sett is not None and local(sett, place.tz) > up[0].when:
        set_at = local(sett, place.tz)
        bits.append(f"sets {words.clock(set_at, n.evening)} in the {words.compass(altaz(moon, set_at, place)[1])}")
    elif up[-1].when == dark[-1].when:
        bits.append("up until dawn")
    glare = " Its light will hide fainter stars." if lit > 0.6 else ""
    return f"Moon: {name}, {pct}% lit, {', '.join(bits)}.{glare} Next: {next_phase}.", lit


# ---------------------------------------------------------------- reports


@dataclass(frozen=True)
class Report:
    text: str
    payload: dict


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _planet_line(
    key: str, p: Pass, mag: float, constellation: str | None, n: Night, when: datetime, place: Place
) -> str:
    name = key.capitalize()
    where = f", in {constellation}" if constellation else ""
    if key in ("uranus", "neptune"):
        tool = "binoculars" if key == "uranus" else "a telescope"
        if p.visible:
            return f"{name}: up tonight{where}, but it needs {tool} (magnitude {mag:.1f})."
        return f"{name}: not well placed tonight."
    if not p.visible:
        body = PLANETS[key]
        if ae.AngleFromSun(body, atime(when)) < 15:
            reason = "too close to the Sun"
        elif p.peak.alt < 5:
            reason = "below the horizon all night"
        else:
            reason = "only up in daylight or twilight"
        return f"{name}: not visible tonight ({reason})."
    return f"{name}: {words.brightness(mag)} (magnitude {mag:.1f}{where}). {_sentence(describe_pass(p, n.evening))}."


def bright_stars_at(
    when: datetime, place: Place, max_mag: float = 1.6, min_alt: float = 10
) -> list[tuple[Star, float, float]]:
    t = atime(when)
    rot = ae.Rotation_EQJ_HOR(t, place.observer)
    out = []
    for star in catalog().bright_named_stars(max_mag):
        alt, az = fixed_altaz(star.ra, star.dec, t, rot)
        if alt >= min_alt:
            out.append((star, alt, az))
    return out


def sky_tonight(place: Place, evening: date, now: datetime) -> Report:
    n = night_of(evening, place)
    when = default_view_time(n, place, now)
    cat = catalog()
    sun_target = cat.planet_target("sun")
    sun = track(sun_target, n.start, n.end, place)
    base = n.evening

    lines = [
        f"Night sky for {place.label} ({words.coords(place.lat, place.lon)}), night of "
        f"{words.day_label(evening)}. Times are {place.tz.key}."
    ]
    if n.polar == "day":
        lines.append("The Sun doesn't set tonight here, so the sky stays bright; only the Moon and maybe Venus show.")
    elif n.polar == "night":
        lines.append("The Sun doesn't rise here today, so it's dark around the clock.")
    else:
        sun_bits = []
        if n.sunset:
            sun_bits.append(f"sets {words.clock(n.sunset, base)}")
        if n.dusk and n.dawn:
            sun_bits.append(f"fully dark {words.clock(n.dusk, base)} to {words.clock(n.dawn, base)}")
        elif n.sunset:
            sun_bits.append("it never gets fully dark tonight (twilight lasts all night)")
        if n.sunrise:
            sun_bits.append(f"rises {words.clock(n.sunrise, base)}")
        lines.append(f"Sun: {', '.join(sun_bits)}.")

    moon_line, moon_lit = moon_summary(n, place, sun, when)
    lines.append(moon_line)

    lines.append("Planets:")
    notes: dict[str, str] = {}
    visible_now: list[tuple[float, str, float, float]] = []
    for key in PLANETS:
        target = cat.planet_target(key)
        mag = magnitude(target, when)
        p = night_pass(target, n, place, sun, mag)
        lines.append(f"- {_planet_line(key, p, mag, constellation_of(target, when, place), n, when, place)}")
        best = best_of(p)
        if best is not None:
            notes[key] = f"Highest {words.clock(best.when, base)}"
            if p.set and p.set.when > best.when:
                notes[key] += f" · sets {words.clock(p.set.when, base)}"
        alt, az = altaz(target, when, place)
        if key in NAKED_EYE_PLANETS and alt >= 8 and dark_enough(sun_altitude(when, place), mag):
            visible_now.append((mag, key, alt, az))

    stars = sorted(bright_stars_at(when, place), key=lambda s: s[0].mag)[:7]
    if stars and sun_altitude(when, place) <= -9:
        listed = ", ".join(f"{s.name} ({words.compass(az)}, {words.height_word(alt)})" for s, alt, az in stars)
        lines.append(f"Bright stars at {words.clock(when, base)}: {listed}.")

    if sun_altitude(when, place) <= -15 and moon_lit < 0.5:
        picks = []
        t = atime(when)
        rot = ae.Rotation_EQJ_HOR(t, place.observer)
        for sid in SHOWPIECES:
            sight = cat.sights[sid]
            alt, az = fixed_altaz(sight.ra, sight.dec, t, rot)
            if alt >= 25:
                picks.append(f"{sight.name} ({words.compass(az)}, {words.height_word(alt)}): {sight.note}")
        if picks:
            lines.append(f"Also worth a look: {'; '.join(picks[:2])}.")

    active = [(s, peak) for s, peak in showers.active_on(evening) if abs((peak - evening).days) <= 10]
    if active:
        lines.append("Meteor showers: " + " ".join(showers.describe(s, peak, place.lat, evening) for s, peak in active))

    if visible_now:
        _, key, alt, az = min(visible_now)
        facing, focus, highlight = az, alt, [key]
    else:
        facing, focus, highlight = (180.0 if place.lat >= 0 else 0.0), None, []
    lines.append(
        f"The sky view shows {words.clock(when, base)}, facing {words.compass(facing)}; "
        "drag the time slider to watch the night go by."
    )

    payload = view_payload(
        view="tonight", place=place, n=n, when=when, facing=facing, focus_alt=focus, highlight=highlight, notes=notes
    )
    return Report("\n".join(lines), payload)


def find(target: Target, place: Place, when: datetime) -> Report:
    n = night_of(evening_of(when), place)
    sun = track(catalog().planet_target("sun"), n.start, n.end, place)
    alt, az = altaz(target, when, place)
    mag = magnitude(target, when)
    constellation = constellation_of(target, when, place)
    base = when.date()

    lines = [
        f"{target.name[0].upper()}{target.name[1:]} from {place.label} at {words.clock(when)} "
        f"on {words.day_label(when.date())} ({place.tz.key}):"
    ]
    if target.kind == "sun":
        lines.append("Never look straight at the Sun.")
    if alt > 0:
        lines.append(f"Up now: {words.direction_phrase(az)}, {round(alt)}° above the horizon ({words.fists(alt)}).")
    else:
        lines.append("Below the horizon right now.")

    facts = []
    if target.kind == "moon":
        lit = ae.Illumination(ae.Body.Moon, atime(when)).phase_fraction
        facts.append(f"{moon_phase_name(ae.MoonPhase(atime(when)))}, {round(lit * 100)}% lit")
    elif mag is not None and target.kind not in ("constellation", "sun"):
        facts.append(f"{words.brightness(mag)} (magnitude {mag:.1f})")
    if constellation:
        facts.append(f"in {constellation}")
    if target.note:
        facts.append(target.note)
    if target.kind == "constellation" and target.stars:
        facts.append("look for " + ", ".join(s.label for s in target.stars[:2]))
    elif target.kind == "asterism":
        facts.append("made of " + ", ".join(s.label for s in target.stars))
    if facts:
        lines.append(f"{'; '.join(facts)[0].upper()}{'; '.join(facts)[1:]}.")

    view_time = when
    if target.kind != "sun":
        vis_mag = mag if mag is not None else 3.0
        p = night_pass(target, n, place, sun, vis_mag)
        if p.visible:
            lines.append(f"Tonight: {describe_pass(p, base)}.")
            best = best_of(p)
            if alt <= 0 and best is not None:
                view_time = best.when
        else:
            day_track = track(target, n.start, n.start + timedelta(hours=24), place)
            if all(s.alt > 0 for s in day_track):
                lines.append("Tonight: it never sets from here, but the sky isn't dark enough to see it well.")
            elif all(s.alt <= 0 for s in day_track):
                lines.append("It never rises from here; it's too far south (or north) for your latitude.")
            elif target.body is not None and ae.AngleFromSun(target.body, atime(when)) < 15:
                lines.append("Tonight: not visible, it's too close to the Sun.")
            else:
                lines.append("Tonight: not visible; it's only up in daylight or twilight.")
    else:
        rise = n.sunrise.strftime("%H:%M") if n.sunrise else None
        sett = n.sunset.strftime("%H:%M") if n.sunset else None
        lines.append(f"Sunset {sett or 'none'} and sunrise {rise or 'none'} (local).")

    if view_time != when:
        lines.append(f"The sky view shows {words.clock(view_time, base)}, when it's best placed.")
    view_alt, view_az = altaz(target, view_time, place)
    fixed = target.is_fixed and target.kind != "star"
    payload = view_payload(
        view="find",
        place=place,
        n=n,
        when=view_time if n.start <= view_time <= n.end else _clamp(view_time, n),
        facing=view_az,
        focus_alt=view_alt,
        highlight=[target.id] + [s.id for s in target.stars],
        markers=[target] if fixed else [],
        notes={},
    )
    return Report("\n".join(lines), payload)


def _clamp(when: datetime, n: Night) -> datetime:
    return min(max(when, n.start), n.end)


def identify(place: Place, when: datetime, azimuth: float, height: tuple[float, float] | None) -> Report:
    n = night_of(evening_of(when), place)
    cat = catalog()
    sun_alt = sun_altitude(when, place)
    t = atime(when)
    rot = ae.Rotation_EQJ_HOR(t, place.observer)

    found: list[tuple[float, Target, float, float, float]] = []

    def offset(alt: float, az: float) -> tuple[float, float] | None:
        """How far an object is from where the person is looking, or None if it's not that way."""
        if alt < 0.5:
            return None
        daz = 0.0 if alt > 82 else abs(((az - azimuth + 180) % 360) - 180)
        dalt = 0.0
        if height is not None:
            low, high = height
            dalt = 0.0 if low <= alt <= high else min(abs(alt - low), abs(alt - high))
        if daz > 45 or dalt > 12:
            return None
        return daz, dalt

    def consider(target: Target, alt: float, az: float, mag: float) -> None:
        off = offset(alt, az)
        if off is None or not dark_enough(sun_alt, mag):
            return
        # People ask about what caught their eye, and their sense of direction is rough,
        # so brightness counts for more than an exact match on direction.
        score = 0.4 * off[0] + 0.6 * off[1] + 10 * mag
        found.append((score, target, alt, az, mag))

    for key in PLANETS:
        if key in ("uranus", "neptune"):
            continue
        target = cat.planet_target(key)
        alt, az = altaz(target, when, place)
        consider(target, alt, az, magnitude(target, when))
    for star in cat.bright_named_stars(2.6):
        alt, az = fixed_altaz(star.ra, star.dec, t, rot)
        consider(cat.star_target(star), alt, az, star.mag)
    moon_alt, moon_az = altaz(cat.planet_target("moon"), when, place)
    moon_that_way = offset(moon_alt, moon_az) is not None

    found.sort(key=lambda f: f[0])
    top = found[:4]
    lines = [
        f"Looking {words.compass(azimuth)}"
        + (f", {round(height[0])}–{round(height[1])}° up" if height else "")
        + f" from {place.label} at {words.clock(when)} on {words.day_label(when.date())} ({place.tz.key}):"
    ]
    if sun_alt > 0:
        lines.append("The Sun is up, so only the Moon, Venus and sometimes Jupiter can show.")
    if not top:
        lines.append(
            "Nothing bright is in that part of the sky right now. A bright light there could be a plane, "
            "a satellite or a drone; planes blink, satellites glide steadily without blinking."
        )
    else:
        _, best, alt, az, mag = top[0]
        kind = {
            "planet": "a planet, which shines steadily instead of twinkling",
            "moon": "the Moon",
            "star": "a star",
        }[best.kind]
        lines.append(
            f"Most likely {best.name}: {kind}, {words.brightness(mag)} (magnitude {mag:.1f}), "
            f"{round(alt)}° up {words.direction_phrase(az)} ({words.fists(alt)})."
        )
        others = [
            f"{tgt.name} ({round(a)}° up {words.direction_phrase(z)}, magnitude {m:.1f})" for _, tgt, a, z, m in top[1:]
        ]
        if others:
            lines.append("Other bright objects that way: " + "; ".join(others) + ".")
        lines.append(
            "If it moves across the sky it's a plane or a satellite. Stars near the horizon can "
            "twinkle and flash colors; planets usually don't."
        )
    if moon_that_way:
        lines.append(f"The Moon is also that way, {round(moon_alt)}° up {words.direction_phrase(moon_az)}.")

    payload = view_payload(
        view="identify",
        place=place,
        n=n,
        when=_clamp(when, n),
        facing=azimuth,
        focus_alt=None if height is None else sum(height) / 2,
        highlight=[tgt.id for _, tgt, *_ in top[:3]],
        markers=[],
        notes={},
    )
    return Report("\n".join(lines), payload)


def meteor_showers(day: date, latitude: float | None) -> str:
    lines = [f"Meteor showers as of {words.day_label(day)}:"]
    active = showers.active_on(day)
    if active:
        lines.append("Active now:")
        lines += [f"- {showers.describe(s, peak, latitude, day)}" for s, peak in active]
    lines.append("Coming up:")
    shown = {s.name for s, _ in active}
    upcoming = [(s, peak) for s, peak in showers.upcoming(day, 5) if s.name not in shown][:3]
    lines += [f"- {showers.describe(s, peak, latitude)}" for s, peak in upcoming]
    lines.append(
        "Best viewing: after midnight, far from city lights, lying back to see the whole sky. "
        "Give your eyes 20 minutes to adjust; no telescope needed."
    )
    return "\n".join(lines)
