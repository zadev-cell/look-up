"""Entry point for hosts that load a server from a file.

- `fastmcp run main.py:mcp` uses the FastMCP server.
- Vercel (or any ASGI host) serves `app`: the MCP endpoint at /mcp plus the landing, privacy and demo pages.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from look_up.server import mcp  # noqa: E402

# Stateless: serverless hosts run many short-lived copies that don't share sessions, so each request stands alone.
app = mcp.http_app(stateless_http=True)

__all__ = ["app", "mcp"]
