from look_up.catalog import catalog


def test_planets_and_moon():
    assert catalog().resolve("Saturn").kind == "planet"
    assert catalog().resolve("saturne").name == "Saturn"
    assert catalog().resolve("the Moon").kind == "moon"


def test_star_names_and_aliases():
    cat = catalog()
    assert cat.resolve("Vega").stars[0].hip == 91262
    assert cat.resolve("north star").name == "Polaris"
    # Two stars are called Markab in the data; the Bayer alpha (in Pegasus) wins.
    assert cat.resolve("markab").stars[0].desig.startswith("α")


def test_constellations():
    cat = catalog()
    orion = cat.resolve("Orion")
    assert orion.kind == "constellation"
    assert {"Betelgeuse", "Rigel"} <= {s.name for s in orion.stars}
    assert cat.resolve("Great Bear").id == "con:UMa"
    assert cat.resolve("southern cross").id == "con:Cru"
    assert cat.resolve("the constellation Lyra").id == "con:Lyr"


def test_sights_and_asterisms():
    cat = catalog()
    assert cat.resolve("M42").name == "the Orion Nebula"
    assert cat.resolve("seven sisters").id == "dso:m45"
    dipper = cat.resolve("big dipper")
    assert dipper.kind == "asterism"
    assert len(dipper.stars) == 7


def test_unknown_names():
    cat = catalog()
    assert cat.resolve("Satrun") is None
    assert "Saturn" in cat.suggestions("Satrun")
    assert cat.is_satellite("ISS")
