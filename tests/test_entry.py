"""main.py is the file Vercel serves, so it must expose the MCP endpoint and the pages as one ASGI app."""

import importlib.util
from pathlib import Path


def test_main_serves_mcp_and_pages():
    spec = importlib.util.spec_from_file_location("entry", Path(__file__).parent.parent / "main.py")
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)

    paths = {getattr(route, "path", None) for route in entry.app.routes}
    assert {"/mcp", "/", "/privacy", "/licenses", "/demo", "/health"} <= paths
