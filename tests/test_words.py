import pytest

from look_up import words


@pytest.mark.parametrize(("az", "word"), [(0, "north"), (44, "northeast"), (225, "southwest"), (359, "north")])
def test_compass(az, word):
    assert words.compass(az) == word


def test_direction_phrase():
    assert words.direction_phrase(181) == "due south"
    assert words.direction_phrase(200) == "in the south"
    assert words.direction_phrase(358) == "due north"


@pytest.mark.parametrize(
    ("alt", "text"),
    [(2, "right on the horizon"), (7, "about half a fist up"), (10, "about 1 fist up"), (45, "about 4½ fists up")],
)
def test_fists(alt, text):
    assert words.fists(alt) == text


@pytest.mark.parametrize(
    ("text", "az"),
    [
        ("SW", 225),
        ("south-west", 225),
        ("South West", 225),
        ("sud ouest", 225),
        ("270", 270),
        ("the north east", 45),
        ("135°", 135),
        ("WNW", 292.5),
    ],
)
def test_parse_direction(text, az):
    assert words.parse_direction(text) == az


def test_parse_direction_rejects_nonsense():
    with pytest.raises(ValueError, match="isn't a direction"):
        words.parse_direction("up-ish")


@pytest.mark.parametrize(
    ("text", "span"),
    [("low", (0, 25)), ("overhead", (70, 90)), ("straight up", (75, 90)), ("30", (20, 40)), ("halfway up", (25, 60))],
)
def test_parse_height(text, span):
    assert words.parse_height(text) == span


def test_parse_height_rejects_out_of_range():
    with pytest.raises(ValueError):
        words.parse_height("120")
    with pytest.raises(ValueError, match="isn't a height"):
        words.parse_height("somewhere")
