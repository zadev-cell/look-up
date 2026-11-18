import httpx
import pytest
from fastmcp import Client

from look_up.server import VIEW_URI, app_html, mcp, sdk_as_global

PARIS = {"latitude": 48.8566, "longitude": 2.3522, "timezone": "Europe/Paris", "place": "Paris"}


async def test_tools_are_labeled_for_the_directory():
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) == {"sky_tonight", "find_object", "identify_object", "meteor_showers"}
    for tool in tools.values():
        assert tool.title
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
    for name in ("sky_tonight", "find_object", "identify_object"):
        assert tools[name].meta["ui"]["resourceUri"] == VIEW_URI


async def test_sky_view_resource():
    async with Client(mcp) as client:
        result = await client.read_resource_mcp(VIEW_URI)
    content = result.contents[0]
    assert content.mime_type == "text/html;profile=mcp-app"
    assert "globalThis.McpApps={" in content.text
    assert "__SKY_DATA__" not in content.text and "/*__MCP_APPS_SDK__*/" not in content.text
    assert content.text == app_html()


def test_sdk_as_global():
    source = "var a=1;function b(){}export{a as App,b};"
    assert sdk_as_global(source) == "var a=1;function b(){}globalThis.McpApps={App:a,b:b};"
    with pytest.raises(RuntimeError):
        sdk_as_global("var a=1;")


async def test_tool_results_carry_text_and_view_data():
    async with Client(mcp) as client:
        result = await client.call_tool_mcp("sky_tonight", {**PARIS, "date": "2026-11-08"})
    assert not result.is_error
    assert "Saturn" in result.content[0].text
    assert {b["id"] for b in result.structured_content["bodies"]} >= {"sun", "moon", "saturn"}


@pytest.mark.parametrize(
    ("tool", "args", "message"),
    [
        ("sky_tonight", {**PARIS, "timezone": "Paris/France"}, "Unknown time zone"),
        ("find_object", {**PARIS, "name": "Satrun"}, "Did you mean Saturn"),
        ("find_object", {**PARIS, "name": "ISS"}, "doesn't track satellites"),
        ("identify_object", {**PARIS, "direction": "up-ish"}, "isn't a direction"),
        ("find_object", {**PARIS, "name": "Mars", "time": "tomorrow"}, "isn't a date and time"),
        ("meteor_showers", {"date": "2300-01-01"}, "between the years 1900 and 2100"),
    ],
)
async def test_errors_say_how_to_fix_the_input(tool, args, message):
    async with Client(mcp) as client:
        result = await client.call_tool_mcp(tool, args)
    assert result.is_error
    assert message in result.content[0].text


async def test_web_pages():
    transport = httpx.ASGITransport(app=mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        home = await http.get("/")
        assert home.status_code == 200 and "http://test/mcp" in home.text
        assert (await http.get("/privacy")).status_code == 200
        assert (await http.get("/demo")).status_code == 200
        assert "globalThis.McpApps" in (await http.get("/demo/view.html")).text
        call = await http.post("/demo/call", json={"name": "find_object", "arguments": {**PARIS, "name": "Vega"}})
        assert call.json()["structuredContent"]["view"] == "find"
        refused = await http.post("/demo/call", json={"name": "meteor_showers", "arguments": {}})
        assert refused.status_code == 400
        icon = await http.get("/icon.png")
        assert icon.headers["content-type"] == "image/png" and icon.content.startswith(b"\x89PNG")


def test_server_has_an_icon_for_claude():
    assert [icon.src for icon in mcp.icons] == ["https://look-up-three.vercel.app/icon.png"]


def test_every_served_view_carries_the_licenses():
    from look_up.server import third_party_notices

    html = app_html()
    assert third_party_notices() in html[: html.index("<html")]


def test_notices_hold_every_license_text():
    from look_up.server import third_party_notices

    notices = third_party_notices()
    assert "Redistribution and use in source and binary forms" in notices  # BSD-3-Clause (star data)
    assert "Apache License" in notices and "Version 2.0" in notices  # MCP Apps SDK
    assert notices.count("Permission is hereby granted, free of charge") == 3  # MIT: MCP SDK, Zod, cfworker
    assert "CC BY 4.0" in notices  # IAU constellation figures


async def test_licenses_page():
    transport = httpx.ASGITransport(app=mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        page = await http.get("/licenses")
    assert page.status_code == 200
    for marker in ("BSD-3-Clause", "CC BY 4.0", "Apache License", "MIT License", "Sky &amp; Telescope"):
        assert marker in page.text
