"""Web pages served next to the MCP endpoint: landing, privacy policy, and a live demo.

The demo page plays the part of Claude: it loads the sky view in an iframe and
speaks the MCP Apps protocol to it, so anyone can try the view in a browser.
"""

from __future__ import annotations

import json
from html import escape

from fastmcp import Client, FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from . import __version__

DEMO_TOOLS = {"sky_tonight", "find_object", "identify_object"}
ICON = (
    '<link rel="icon" href="data:image/svg+xml,'
    "%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E"
    "%3Cpath d=%27M12 2l1.9 5.8L20 9.7l-5 3.6 1.9 5.9L12 15.6l-4.9 3.6L9 13.3 4 9.7l6.1-1.9z%27 "
    "fill=%27%23ffd27a%27/%3E"
    '%3C/svg%3E">'
)
CONTACT = "https://github.com/zadev-cell/look-up/issues"

STYLE = """
:root { color-scheme: dark; --bg: #070b16; --panel: #0e1528; --line: #1f2a44; --text: #e8ecf8;
  --muted: #98a3c0; --accent: #ffd27a; }
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin: 0; min-height: 100vh; background: radial-gradient(1200px 600px at 70% -10%, #16224a 0%, var(--bg) 60%);
  color: var(--text); font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 48px 16px 64px; }
h1 { font-size: 40px; line-height: 1.1; margin: 0 0 8px; letter-spacing: -0.02em; }
h2 { font-size: 20px; margin: 40px 0 8px; }
p, li { color: var(--muted); }
a { color: var(--accent); }
code, .url { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }
.url { display: flex; gap: 8px; align-items: center; background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 10px 12px; color: var(--text); overflow-x: auto; }
.url button { margin-left: auto; flex: none; }
button { background: var(--accent); color: #1a1405; border: 0; border-radius: 8px; padding: 6px 12px;
  font: 600 14px ui-sans-serif, system-ui, sans-serif; cursor: pointer; }
.prompts li { color: var(--text); }
footer { margin-top: 48px; font-size: 13px; color: var(--muted); }
"""


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>{ICON}<style>{STYLE}</style></head>
<body><main>{body}</main></body></html>"""
    return HTMLResponse(html)


def landing(origin: str) -> HTMLResponse:
    url = f"{origin}/mcp"
    return _page(
        "Look Up",
        f"""
<h1>Look Up</h1>
<p>The night sky, inside Claude. Ask what you can see tonight, where to find a planet, or what that bright
"star" is, and get an answer with a live sky chart you can scrub through the night.</p>

<h2>Add it to Claude</h2>
<p>In Claude, open <b>Customize → Connectors → Add custom connector</b> and paste this URL:</p>
<div class="url"><span id="u">{escape(url)}</span>
<button onclick="navigator.clipboard.writeText(document.getElementById('u').textContent)">Copy</button></div>
<p>No account or sign-in needed.</p>

<h2>Try asking</h2>
<ul class="prompts">
<li>What can I see in the sky tonight from Paris?</li>
<li>Where's Saturn right now?</li>
<li>What's that bright star low in the southwest?</li>
<li>When's the next meteor shower, and will the Moon be in the way?</li>
</ul>

<h2>See it without Claude</h2>
<p><a href="/demo">Open the live demo</a>: the same sky view, driven by this page instead of Claude.</p>

<h2>What it knows</h2>
<p>The Sun, the Moon and the planets (computed with <a href="https://github.com/cosinekitty/astronomy">Astronomy
Engine</a>), 2,851 stars down to magnitude 5.5, about 480 named stars, the 88 constellations, famous sights like
the Pleiades and the Andromeda Galaxy, and the major annual meteor showers. It doesn't track satellites.</p>

<footer><a href="/privacy">Privacy</a> · <a href="/licenses">Licenses</a> · <a href="{CONTACT}">Support</a> ·
Version {__version__}<br>
Star and constellation data from d3-celestial (BSD-3-Clause), based on the XHIP catalog and the IAU
constellation charts (CC BY 4.0).
</footer>
""",
    )


def privacy() -> HTMLResponse:
    return _page(
        "Look Up privacy policy",
        f"""
<h1>Privacy policy</h1>
<p>Last updated 8 November 2026.</p>

<h2>What Look Up receives</h2>
<p>When Claude uses Look Up, it sends the inputs of the tool it calls: a latitude and longitude, a time zone, an
optional place name, a date or time, and what you asked about (like a planet's name or a compass direction).
Look Up never receives your conversation, your name, or your account details.</p>

<h2>How it's used</h2>
<p>Only to compute where things are in the sky and send the answer back. Nothing else.</p>

<h2>What's kept</h2>
<p>Look Up doesn't store tool inputs or answers, and it uses no cookies, analytics or trackers. The hosting
provider may keep standard request logs (such as IP address and time) for a short period to run and protect
the service.</p>

<h2>Sharing</h2>
<p>Look Up doesn't sell or share any data, and it doesn't call other services to answer your questions.</p>

<h2>Contact</h2>
<p>Questions: <a href="{CONTACT}">{CONTACT}</a>.</p>
<footer><a href="/">Look Up</a> · <a href="/licenses">Licenses</a></footer>
""",
    )


def licenses() -> HTMLResponse:
    from .server import third_party_notices

    return _page(
        "Look Up licenses",
        f"""
<h1>Licenses</h1>
<p>Look Up is built on other people's open work. Here is what it uses and the license for each.</p>
<pre style="white-space: pre-wrap; font-size: 13px; color: var(--muted)">{escape(third_party_notices())}</pre>
<footer><a href="/">Look Up</a> · <a href="/privacy">Privacy</a></footer>
""",
    )


DEMO_PLACES = [
    ("Paris", 48.8566, 2.3522, "Europe/Paris"),
    ("New York", 40.7128, -74.0060, "America/New_York"),
    ("Sydney", -33.8688, 151.2093, "Australia/Sydney"),
    ("Tokyo", 35.6762, 139.6503, "Asia/Tokyo"),
    ("Reykjavik", 64.1466, -21.9426, "Atlantic/Reykjavik"),
]

DEMO_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Look Up demo</title>__ICON__
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0b0d12; color: #e8ecf8; font: 15px/1.5 ui-sans-serif, system-ui, -apple-system,
  "Segoe UI", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 48px; }
header { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
header h1 { font-size: 18px; margin: 0 auto 0 0; }
select, button { background: #161b26; color: #e8ecf8; border: 1px solid #2a3142; border-radius: 8px;
  padding: 6px 10px; font: inherit; }
.bubble { margin: 0 0 12px auto; max-width: 80%; width: fit-content; background: #1d2433; padding: 10px 14px;
  border-radius: 16px; }
iframe { display: block; width: 100%; height: 480px; border: 0; border-radius: 14px; background: #05070d; }
body.fullscreen iframe { position: fixed; inset: 0; width: 100vw; height: 100vh !important; border-radius: 0;
  z-index: 10; }
details { margin-top: 16px; color: #98a3c0; }
pre { white-space: pre-wrap; background: #11151e; padding: 12px; border-radius: 10px; color: #c9d1e6; }
a { color: #ffd27a; }
</style></head>
<body><main>
<header><h1><a href="/" style="color:inherit;text-decoration:none">Look Up</a> · demo</h1>
<select id="place">__PLACES__</select>
<select id="ask">
  <option value="tonight">What's up tonight?</option>
  <option value="saturn">Where's Saturn?</option>
  <option value="orion">Where's Orion?</option>
  <option value="identify">Bright light in the south?</option>
</select>
<button id="here">Use my location</button></header>
<p class="bubble" id="bubble"></p>
<div id="slot"></div>
<details><summary>What Claude reads</summary><pre id="text"></pre></details>
</main>
<script>
const PLACES = __PLACES_JSON__;
const params = new URLSearchParams(location.search);
let custom = null;

function currentCall() {
  const p = custom || PLACES[document.getElementById("place").selectedIndex];
  const base = { latitude: p.lat, longitude: p.lon, timezone: p.tz, place: p.name };
  if (params.get("time")) base.time = params.get("time");
  const tool = params.get("tool");
  if (tool && !custom) {
    const args = { ...base };
    for (const k of ["name", "direction", "height", "date"]) if (params.get(k)) args[k] = params.get(k);
    if (tool === "sky_tonight") delete args.time;
    return [params.get("q") || `Look Up: ${tool}`, tool, args];
  }
  const ask = document.getElementById("ask").value;
  if (ask === "saturn") return [`Where's Saturn from ${p.name}?`, "find_object", { name: "Saturn", ...base }];
  if (ask === "orion") return [`Where's Orion from ${p.name}?`, "find_object", { name: "Orion", ...base }];
  if (ask === "identify") return [`What's the bright light in the south? I'm in ${p.name}.`, "identify_object",
    { direction: "S", ...base }];
  const t = { ...base }; delete t.time;
  if (params.get("date")) t.date = params.get("date");
  return [`What's in the sky tonight in ${p.name}?`, "sky_tonight", t];
}

async function callTool(name, args) {
  const r = await fetch("/demo/call", { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, arguments: args }) });
  return r.json();
}

let frame = null;
let call = null;

function post(msg) { frame.contentWindow.postMessage(msg, "*"); }
function reply(id, result) { post({ jsonrpc: "2.0", id, result }); }
function notify(method, params) { post({ jsonrpc: "2.0", method, params }); }

function hostContext() {
  const full = document.body.classList.contains("fullscreen");
  return {
    theme: "dark", platform: "web", locale: navigator.language,
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    displayMode: full ? "fullscreen" : "inline", availableDisplayModes: ["inline", "fullscreen"],
    containerDimensions: full ? { width: innerWidth, height: innerHeight } : { maxHeight: 900 },
  };
}

window.addEventListener("message", async (event) => {
  if (!frame || event.source !== frame.contentWindow) return;
  const msg = event.data;
  if (!msg || msg.jsonrpc !== "2.0" || !msg.method) return;
  switch (msg.method) {
    case "ui/initialize":
      reply(msg.id, { protocolVersion: msg.params?.protocolVersion || "2026-01-26",
        hostInfo: { name: "Look Up demo", version: "__VERSION__" },
        hostCapabilities: { openLinks: {}, serverTools: {}, logging: {} }, hostContext: hostContext() });
      break;
    case "ui/notifications/initialized": {
      notify("ui/notifications/tool-input", { arguments: call[2] });
      const result = await callTool(call[1], call[2]);
      document.getElementById("text").textContent =
        (result.content || []).map((c) => c.text || "").join("\\n");
      notify("ui/notifications/tool-result", result);
      break;
    }
    case "ui/notifications/size-changed":
      if (!document.body.classList.contains("fullscreen") && msg.params?.height) {
        frame.style.height = Math.ceil(msg.params.height) + "px";
      }
      break;
    case "ui/request-display-mode": {
      const mode = msg.params?.mode === "fullscreen" ? "fullscreen" : "inline";
      document.body.classList.toggle("fullscreen", mode === "fullscreen");
      reply(msg.id, { mode });
      notify("ui/notifications/host-context-changed", hostContext());
      break;
    }
    case "tools/call":
      reply(msg.id, await callTool(msg.params.name, msg.params.arguments || {}));
      break;
    case "ui/open-link":
      window.open(msg.params.url, "_blank", "noopener");
      reply(msg.id, {});
      break;
    case "ui/message":
    case "ui/update-model-context":
    case "ping":
      reply(msg.id, {});
      break;
    case "notifications/message":
      console.log("[sky view]", msg.params);
      break;
    default:
      if (msg.id !== undefined) post({ jsonrpc: "2.0", id: msg.id, error: { code: -32601, message: "Not supported" } });
  }
});

function run() {
  call = currentCall();
  document.getElementById("bubble").textContent = call[0];
  document.body.classList.remove("fullscreen");
  const slot = document.getElementById("slot");
  slot.innerHTML = "";
  frame = document.createElement("iframe");
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("title", "Sky view");
  frame.src = "/demo/view.html";
  slot.appendChild(frame);
}

document.getElementById("place").addEventListener("change", () => { custom = null; run(); });
document.getElementById("ask").addEventListener("change", run);
document.getElementById("here").addEventListener("click", () => {
  navigator.geolocation.getCurrentPosition((pos) => {
    custom = { name: "your location", lat: +pos.coords.latitude.toFixed(4), lon: +pos.coords.longitude.toFixed(4),
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone };
    run();
  }, () => alert("Couldn't get your location."));
});
if (params.get("place")) document.getElementById("place").value = params.get("place");
if (params.get("ask")) document.getElementById("ask").value = params.get("ask");
run();
</script></body></html>
"""


def demo() -> HTMLResponse:
    options = "".join(f'<option value="{escape(name)}">{escape(name)}</option>' for name, *_ in DEMO_PLACES)
    places = json.dumps([{"name": n, "lat": lat, "lon": lon, "tz": tz} for n, lat, lon, tz in DEMO_PLACES])
    html = (
        DEMO_HTML.replace("__PLACES_JSON__", places)
        .replace("__PLACES__", options)
        .replace("__VERSION__", __version__)
        .replace("__ICON__", ICON)
    )
    return HTMLResponse(html)


def _origin(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"


def register(mcp: FastMCP) -> None:
    from .server import app_html

    @mcp.custom_route("/", methods=["GET"], include_in_schema=False)
    async def home(request: Request) -> Response:
        return landing(_origin(request))

    @mcp.custom_route("/privacy", methods=["GET"], include_in_schema=False)
    async def privacy_page(request: Request) -> Response:
        return privacy()

    @mcp.custom_route("/licenses", methods=["GET"], include_in_schema=False)
    async def licenses_page(request: Request) -> Response:
        return licenses()

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(request: Request) -> Response:
        return PlainTextResponse("ok")

    @mcp.custom_route("/demo", methods=["GET"], include_in_schema=False)
    async def demo_page(request: Request) -> Response:
        return demo()

    @mcp.custom_route("/demo/view.html", methods=["GET"], include_in_schema=False)
    async def demo_view(request: Request) -> Response:
        return HTMLResponse(app_html())

    @mcp.custom_route("/demo/call", methods=["POST"], include_in_schema=False)
    async def demo_call(request: Request) -> Response:
        try:
            body = await request.json()
            name, arguments = body["name"], body.get("arguments") or {}
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": 'Send JSON like {"name": ..., "arguments": {...}}.'}, status_code=400)
        if name not in DEMO_TOOLS or not isinstance(arguments, dict):
            return JSONResponse({"error": "Unknown tool."}, status_code=400)
        async with Client(mcp) as client:
            result = await client.call_tool_mcp(name, arguments)
        return JSONResponse(result.model_dump(mode="json", by_alias=True, exclude_none=True))
