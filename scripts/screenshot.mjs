// Screenshot the Look Up demo with headless Chrome over the DevTools protocol.
// It waits until the tool result has arrived, unlike Chrome's --screenshot flag.
//
// Usage: node scripts/screenshot.mjs <out.png> <url> [width] [height] [actions-json]
//   CLIP=iframe crops to the sky view (what the directory listing wants).
//   actions: [{"click":[x,y]}, {"drag":[x1,y1,x2,y2]}, {"wait":ms}, {"eval":"js in page"}]
// Example:
//   CLIP=iframe node scripts/screenshot.mjs docs/screenshots/orion.png \
//     "http://127.0.0.1:8000/demo?place=Paris&tool=find_object&name=Orion&time=2026-11-08T23:30" 760 760
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [out, url, width = "800", height = "720", actionsJson = "[]"] = process.argv.slice(2);
const actions = JSON.parse(actionsJson);
const profile = mkdtempSync(join(tmpdir(), "look-up-chrome-"));
const port = 9333;
const chromePath = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const chrome = spawn(chromePath, [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--hide-scrollbars",
  "--no-first-run", "--no-default-browser-check", "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    target = list.find((t) => t.type === "page");
    if (target) break;
  } catch {}
  await sleep(200);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const pending = new Map();
const logs = [];
ws.addEventListener("message", (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.consoleAPICalled") logs.push(`console.${msg.params.type}: ${msg.params.args.map((a) => a.value ?? a.description).join(" ")}`);
  if (msg.method === "Runtime.exceptionThrown") logs.push(`EXCEPTION: ${msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text}`);
  if (msg.method === "Log.entryAdded") logs.push(`log.${msg.params.entry.level}: ${msg.params.entry.text}`);
});
const send = (method, params = {}) => new Promise((r) => { const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });

await send("Runtime.enable");
await send("Log.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: +width, height: +height, deviceScaleFactor: 2, mobile: false });
await send("Page.navigate", { url });

// Wait for the tool result (the demo shows "What Claude reads" text when it arrives).
let ready = false;
for (let i = 0; i < 60 && !ready; i++) {
  await sleep(250);
  const r = await send("Runtime.evaluate", { expression: "document.getElementById('text')?.textContent.length || 0", returnByValue: true });
  ready = (r.result?.result?.value || 0) > 0;
}
await sleep(900);

for (const a of actions) {
  if (a.wait) await sleep(a.wait);
  if (a.click) {
    const [x, y] = a.click;
    for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
    await sleep(300);
  }
  if (a.drag) {
    const [x1, y1, x2, y2] = a.drag;
    await send("Input.dispatchMouseEvent", { type: "mousePressed", x: x1, y: y1, button: "left", clickCount: 1 });
    for (let k = 1; k <= 12; k++) {
      await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: x1 + ((x2 - x1) * k) / 12, y: y1 + ((y2 - y1) * k) / 12, button: "left", buttons: 1 });
      await sleep(16);
    }
    await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: x2, y: y2, button: "left", clickCount: 1 });
    await sleep(300);
  }
  if (a.eval) await send("Runtime.evaluate", { expression: a.eval, awaitPromise: true });
}

let clip;
if (process.env.CLIP === "iframe") {
  const r = await send("Runtime.evaluate", { expression: "JSON.stringify(document.querySelector('iframe').getBoundingClientRect())", returnByValue: true });
  const b = JSON.parse(r.result.result.value);
  clip = { x: b.x, y: b.y, width: b.width, height: b.height, scale: 1 };
}
const shot = await send("Page.captureScreenshot", { format: "png", ...(clip ? { clip } : {}) });
writeFileSync(out, Buffer.from(shot.result.data, "base64"));
console.log(`${out} (ready: ${ready})`);
for (const l of logs) console.log("  " + l);
ws.close();
chrome.kill();
await sleep(300);
rmSync(profile, { recursive: true, force: true });
