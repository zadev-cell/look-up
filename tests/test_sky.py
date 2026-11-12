import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from look_up import sky
from look_up.catalog import catalog

PARIS = sky.Place(48.8566, 2.3522, ZoneInfo("Europe/Paris"), "Paris")
SYDNEY = sky.Place(-33.8688, 151.2093, ZoneInfo("Australia/Sydney"), "Sydney")
TROMSO = sky.Place(69.6492, 18.9553, ZoneInfo("Europe/Oslo"), "Tromsø")
EVENING = datetime(2026, 11, 8, 21, 30, tzinfo=PARIS.tz)


def test_night_times_in_paris():
    n = sky.night_of(date(2026, 11, 8), PARIS)
    assert n.sunset.strftime("%H:%M") == "17:19"
    assert n.sunrise.date() == date(2026, 11, 9)
    assert "07:45" <= n.sunrise.strftime("%H:%M") <= "07:55"
    assert n.sunset < n.dusk < n.dawn < n.sunrise
    assert n.start < n.sunset and n.end > n.sunrise


def test_saturn_from_paris():
    alt, az = sky.altaz(catalog().resolve("Saturn"), EVENING, PARIS)
    assert 38 < alt < 44
    assert 155 < az < 175


def test_sky_tonight_report():
    report = sky.sky_tonight(PARIS, date(2026, 11, 8), EVENING)
    assert "Saturn: bright" in report.text
    assert "highest at 22:1" in report.text
    assert "new moon" in report.text
    assert report.payload["highlight"] == ["saturn"]


def test_identify_finds_saturn():
    report = sky.identify(PARIS, EVENING, 180, (25, 60))
    assert "Most likely Saturn" in report.text
    assert report.payload["highlight"][0] == "saturn"


def test_find_below_horizon_points_to_best_time():
    report = sky.find(catalog().resolve("Jupiter"), PARIS, EVENING)
    assert "Below the horizon right now" in report.text
    assert "rises Mon 00:" in report.text
    assert report.payload["time"].startswith("2026-11-09T07:")


def test_southern_hemisphere_faces_north():
    when = datetime(2026, 11, 8, 21, 30, tzinfo=SYDNEY.tz)
    _, az = sky.altaz(catalog().resolve("Saturn"), when, SYDNEY)
    assert az < 90 or az > 270


def test_polar_day_and_night():
    summer = sky.sky_tonight(TROMSO, date(2026, 6, 21), datetime(2026, 6, 21, 12, tzinfo=TROMSO.tz))
    assert "doesn't set" in summer.text
    winter = sky.sky_tonight(TROMSO, date(2026, 12, 21), datetime(2026, 12, 21, 12, tzinfo=TROMSO.tz))
    assert "doesn't rise" in winter.text


def _view_altaz(payload: dict, ra: float, dec: float, t_ms: int) -> tuple[float, float]:
    """The same math the sky view runs in the browser."""
    r, d = math.radians(ra), math.radians(dec)
    v = (math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d))
    m = payload["precession"]
    x, y, z = (m[0][k] * v[0] + m[1][k] * v[1] + m[2][k] * v[2] for k in range(3))
    lst = math.radians(payload["lst0"] + (t_ms - payload["t0"]) * 360.98564736629 / 86400000)
    lat = math.radians(payload["place"]["lat"])
    xh = x * math.cos(lst) + y * math.sin(lst)
    east = -x * math.sin(lst) + y * math.cos(lst)
    north = math.cos(lat) * z - math.sin(lat) * xh
    up = math.sin(lat) * z + math.cos(lat) * xh
    return math.degrees(math.asin(up)), math.degrees(math.atan2(east, north)) % 360


def _interpolate(samples: list, t_ms: int) -> tuple[float, float]:
    for (t0, ra0, dec0), (t1, ra1, dec1) in zip(samples, samples[1:], strict=False):
        if t0 <= t_ms <= t1:
            f = (t_ms - t0) / (t1 - t0)
            dra = ((ra1 - ra0 + 540) % 360) - 180
            return ra0 + dra * f, dec0 + (dec1 - dec0) * f
    raise AssertionError("time outside samples")


@pytest.mark.parametrize("name", ["Saturn", "Moon", "Vega"])
def test_view_math_matches_server(name):
    target = catalog().resolve(name)
    payload = sky.find(target, PARIS, EVENING).payload
    t_ms = sky.epoch_ms(EVENING)
    if target.body is not None:
        body = next(b for b in payload["bodies"] if b["id"] == target.id)
        ra, dec = _interpolate(body["samples"], t_ms)
    else:
        ra, dec = target.ra, target.dec
    alt, az = _view_altaz(payload, ra, dec, t_ms)
    server_alt, server_az = sky.altaz(target, EVENING, PARIS)
    if server_alt > 0:
        assert abs(alt - server_alt) < 0.3
        assert abs(((az - server_az + 180) % 360) - 180) < 0.3
    else:
        assert alt < 0.5
