"""Entry point for hosts that load a server from a file, like `fastmcp run main.py:mcp`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from look_up.server import mcp  # noqa: E402

__all__ = ["mcp"]
