#!/usr/bin/env python3
"""Render the actual four front doors with local-only, unsigned fixtures.

No provider, probe, effector, Gradio computation or verification POST is called.
Three may be supplied from an already installed, exact 0.160.0 package; its
fixed module paths are intercepted locally. Its network delivery is not tested.
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "space"
THREE_FILES = (
    "build/three.module.js",
    "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/postprocessing/EffectComposer.js",
    "examples/jsm/postprocessing/RenderPass.js",
    "examples/jsm/postprocessing/UnrealBloomPass.js",
    "examples/jsm/postprocessing/Pass.js",
    "examples/jsm/postprocessing/ShaderPass.js",
    "examples/jsm/postprocessing/MaskPass.js",
    "examples/jsm/shaders/CopyShader.js",
    "examples/jsm/shaders/LuminosityHighPassShader.js",
)
INSPECT_JS = r"""({ forced }) => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    function rgba(value) {
      if (!CSS.supports('color', value)) throw new Error('Unsupported computed color: ' + value);
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = value; ctx.fillRect(0, 0, 1, 1);
      const c = [...ctx.getImageData(0, 0, 1, 1).data]; c[3] /= 255; return c;
    }
    function over(a, b) { const alpha = a[3] + b[3] * (1 - a[3]); return alpha ? [0, 1, 2].map(i => (a[i] * a[3] + b[i] * b[3] * (1 - a[3])) / alpha).concat(alpha) : [0, 0, 0, 0]; }
    function luminance(c) { return c.slice(0, 3).map(x => x / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4).reduce((n, x, i) => n + x * [.2126, .7152, .0722][i], 0); }
    function ratio(a, b) { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
    const backgrounds = new WeakMap();
    function backdrop(el) {
      if (!el) return [[255, 255, 255, 1]];
      if (backgrounds.has(el)) return backgrounds.get(el);
      const s = getComputedStyle(el), lower = backdrop(el.parentElement), base = lower.map(c => over(rgba(s.backgroundColor), c));
      const colors = s.backgroundImage === 'none' ? [] : (s.backgroundImage.match(/(?:rgba?|color)\([^()]+\)/g) || []).map(rgba);
      const values = colors.length ? base.flatMap(c => [c, ...colors.map(stop => over(stop, c))]) : base;
      const unique = [...new Map(values.map(c => [c.map(x => Math.round(x)).join(','), c])).values()].slice(0, 24);
      backgrounds.set(el, unique); return unique;
    }
    function visible(el) { return el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) && el.getBoundingClientRect().height > 0; }
    function boundedScroller(el) { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) { const s = getComputedStyle(p), r = p.getBoundingClientRect(); if (/(auto|scroll)/.test(s.overflowX) && r.left >= -1 && r.right <= innerWidth + 1) return true; } return false; }
    const textFailures = [], overflow = [], uncertain = [];
    let textPairs = 0;
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let text; (text = walk.nextNode());) {
      const label = text.textContent.trim(), el = text.parentElement;
      if (!label || !el || el.closest('script,style,svg,.visually-hidden[aria-hidden="true"]') || !visible(el) || el.closest('[disabled]')) continue;
      const s = getComputedStyle(el), range = document.createRange(); range.selectNodeContents(text);
      const rect = range.getBoundingClientRect(); if (!rect.width || !rect.height) continue;
      if ((rect.left < -1 || rect.right > innerWidth + 1) && !boundedScroller(el) && !el.closest('.skip-link,.kanchay-skip,.skip,.native-skip')) overflow.push({ text: label.slice(0, 90), left: rect.left, right: rect.right });
      if (forced) continue;
      if (Number(s.opacity) !== 1) { uncertain.push(label.slice(0, 70)); continue; }
      const foreground = rgba(s.color), bg = backdrop(el), measured = Math.min(...bg.map(c => ratio(over(foreground, c), c)));
      const large = Number.parseFloat(s.fontSize) >= 24 || (Number.parseFloat(s.fontSize) >= 18.6667 && Number.parseFloat(s.fontWeight) >= 700);
      const minimum = large ? 3 : 4.5; textPairs++;
      if (measured < minimum) textFailures.push({ text: label.slice(0, 110), foreground: s.color, ratio: +measured.toFixed(3), minimum });
    }
    const targets = [], unlabeled = [];
    for (const el of document.querySelectorAll('button,input:not([type="hidden"]),select,textarea,nav a')) {
      if (!visible(el)) continue;
      const box = (el.matches('input[type="checkbox"]') && el.closest('label') || el).getBoundingClientRect();
      if (!el.disabled && (box.width < 43.9 || box.height < 43.9)) targets.push({ text: (el.textContent || el.getAttribute('aria-label') || el.name).trim().slice(0, 90), tag: el.tagName, width: box.width, height: box.height });
      if (el.matches('button,input,select,textarea') && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby') && !el.labels?.length && !el.textContent.trim() && !el.getAttribute('title')) unlabeled.push(el.outerHTML.slice(0, 200));
    }
    return { viewport: innerWidth, documentWidth: document.documentElement.scrollWidth, consoleContentWidth: document.querySelector('.console-title')?.getBoundingClientRect().width ?? null, h1Count: [...document.querySelectorAll('h1')].filter(visible).length, textPairs, textFailures, uncertain, overflow, targets, unlabeled, animations: document.getAnimations().filter(a => a.playState === 'running').length };
  }"""


def serve(port: int):
    """The real ASGI app; all external transport and operational reads denied."""
    def network_boundary(event, arguments):
        if event == "socket.connect" and isinstance(arguments[1], tuple):
            if arguments[1][0] not in {"127.0.0.1", "::1", "localhost", "testserver"}:
                raise RuntimeError("External transport forbidden during frontend qualification")
    sys.addaudithook(network_boundary)
    sys.path.insert(0, str(SPACE))
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    os.environ["HF_HUB_OFFLINE"] = "1"
    import app as constellation
    from fastapi.responses import JSONResponse
    import uvicorn

    @constellation.app.middleware("http")
    async def read_only(request, call_next):
        if request.method not in {"GET", "HEAD"} or request.url.path.startswith("/api/") or request.url.path in {"/healthz", "/readyz"}:
            return JSONResponse({"state": "UNAVAILABLE", "detail": "LOCAL_READ_ONLY_QA_FIXTURE"}, status_code=503)
        return await call_next(request)

    uvicorn.run(constellation.app, host="127.0.0.1", port=port, log_level="warning")


def sample_scenario():
    previous = "0" * 64
    events = []
    for seq in range(2):
        event = {"seq": seq, "t": seq, "track": seq + 1, "kind": "spawn", "r": 30, "theta": 0, "cls": "unknown", "truth": "LOCAL_QA_SYNTHETIC"}
        body = json.dumps(event, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256((previous + body).encode()).hexdigest()
        events.append({**event, "prev_hash": previous, "chain_hash": digest})
        previous = digest
    return {"state": "MEASURED", "seed": 7, "events": events, "terminal": previous,
            "receipt": {"sha256": "a" * 64}, "truth": "LOCAL_QA_SYNTHETIC"}


async def qualify(args):
    from playwright.async_api import async_playwright

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    origin = "http://127.0.0.1:" + str(args.port)
    checks, observations, intercepted = [], [], []
    source = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(),
        "local_changes": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines(),
        "claim": "Unsigned local rendered observations; no provider or operational qualification",
    }
    if os.environ.get("SOURCE_REVISION") and os.environ["SOURCE_REVISION"] != source["commit"]:
        raise RuntimeError("Declared source revision does not match the actual checkout")
    three = {}
    if args.three_root:
        package = args.three_root.resolve()
        if json.loads((package / "package.json").read_text())["version"] != "0.160.0":
            raise RuntimeError("Only the actual pinned Three 0.160.0 package is supported")
        for relative in THREE_FILES:
            data = (package / relative).read_bytes()
            if len(data) > 2_000_000:
                raise RuntimeError("Pinned QA module exceeds its bound")
            three["/three@0.160.0/" + relative] = data
        source["three_0_160_0_sha256"] = {key: hashlib.sha256(value).hexdigest() for key, value in three.items()}

    def check(name, passed, detail=None):
        checks.append({"name": name, "pass": bool(passed), "detail": detail})

    def inspect_result(name, result):
        observations.append({"name": name, **result})
        check(name + ": reflow, text contrast, controls and labels",
              result["documentWidth"] <= result["viewport"] + 1 and result["h1Count"] == 1
              and not result["animations"]
              and (result["consoleContentWidth"] is None or result["viewport"] > 640
                   or result["consoleContentWidth"] >= result["viewport"] - 48)
              and not any(result[key] for key in ("overflow", "targets", "unlabeled", "textFailures", "uncertain")), result)

    environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR") if key in os.environ}
    environment.update(GRADIO_ANALYTICS_ENABLED="false", HF_HUB_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    with (output / "local-runtime.log").open("w") as log:
        server = subprocess.Popen([args.runtime_python, str(Path(__file__).resolve()), "--serve", "--port", str(args.port)], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            ready = False
            for _ in range(180):
                if server.poll() is not None:
                    break
                try:
                    connection = HTTPConnection("127.0.0.1", args.port, timeout=1)
                    connection.request("GET", "/")
                    response = connection.getresponse()
                    response.read()
                    ready = response.status == 200
                    connection.close()
                    if ready:
                        break
                except OSError:
                    pass
                await asyncio.sleep(.25)
            if not ready:
                raise RuntimeError("Actual local runtime did not start; inspect local-runtime.log")
            async with async_playwright() as playwright:
                launch = {"headless": True, "args": ["--disable-dev-shm-usage", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]}
                if args.browser:
                    launch["executable_path"] = args.browser
                browser = await playwright.chromium.launch(**launch)

                async def open_page(path, width=1280, theme="dark", mode="normal", **extra):
                    context = await browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce", **extra)
                    await context.add_init_script("localStorage.setItem('szl-constellation-appearance', " + json.dumps(theme) + ")")
                    page = await context.new_page()
                    errors, writes = [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    state = {"mode": mode}

                    async def intercept(route):
                        request = route.request
                        url = urlsplit(request.url)
                        if request.method not in {"GET", "HEAD"}:
                            writes.append(request.method + " " + url.path)
                            await route.abort()
                        elif url.hostname == "unpkg.com" and url.path in three and state["mode"] != "no-library":
                            await route.fulfill(status=200, content_type="text/javascript", headers={"Access-Control-Allow-Origin": "*"}, body=three[url.path])
                        elif url.netloc != "127.0.0.1:" + str(args.port):
                            intercepted.append({"path": url.path, "host": url.hostname, "mode": state["mode"]})
                            await route.abort()
                        elif state["mode"] == "manifest-failed" and url.path in {"/static/estates.json", "/estates.json"}:
                            await route.fulfill(status=503, content_type="application/json", body='{"state":"UNAVAILABLE","detail":"LOCAL_QA_FIXTURE"}')
                        elif url.path == "/api/c2/scenario" and state["mode"] == "scenario":
                            await route.fulfill(status=200, content_type="application/json", body=json.dumps(sample_scenario()))
                        elif url.path.startswith("/api/") or url.path in {"/readyz", "/healthz"}:
                            await route.fulfill(status=503, content_type="application/json", body='{"state":"UNAVAILABLE","detail":"LOCAL_QA_FIXTURE"}')
                        else:
                            await route.continue_()
                    await context.route("**/*", intercept)
                    await page.goto(origin + path, wait_until="domcontentloaded", timeout=30000)
                    await page.locator("h1").wait_for(timeout=30000)
                    await page.get_by_role("button", name="Switch to " + ("light" if theme == "dark" else "dark") + " theme").wait_for(timeout=15000)
                    if path == "/":
                        await page.wait_for_function("!document.getElementById('boot') || getComputedStyle(document.getElementById('boot')).display === 'none'", timeout=20000)
                        await page.wait_for_function("!document.getElementById('directory-status').textContent.startsWith('Loading')", timeout=15000)
                    elif path == "/holo/demo.html":
                        await page.wait_for_function("!document.getElementById('fabric-message').textContent.startsWith('Loading')", timeout=15000)
                    if path == "/panels/":
                        await page.get_by_role("button", name="Measure family drift", exact=True).wait_for(timeout=30000)
                    await page.wait_for_timeout(150)
                    return context, page, errors, writes, state

                widths = [320, 1280] if args.quick else [320, 375, 768, 1280, 1920]
                pages = [("/", "map"), ("/c2", "c2"), ("/holo/demo.html", "fabric"), ("/panels/", "panels")]
                if args.surface != "all":
                    pages = [item for item in pages if item[1] == args.surface]
                for path, name in pages:
                    for width in widths:
                        for theme in ("dark", "light"):
                            context, page, errors, writes, _ = await open_page(path, width, theme)
                            label = f"{name} {width}px {theme}"
                            inspect_result(label, await page.evaluate(INSPECT_JS, {"forced": False}))
                            check(label + ": no script errors or operational writes", not errors and not writes, {"errors": errors, "writes": writes})
                            check(label + ": reduced-motion state", await page.evaluate("document.documentElement.dataset.motion === 'paused' && document.getAnimations().every(a => a.playState !== 'running')"))
                            if path == "/panels/" and width == 320:
                                await page.keyboard.press("Tab")
                                check(label + ": skip link is first in keyboard navigation", await page.evaluate("document.activeElement.classList.contains('console-skip')"))
                                await page.keyboard.press("Enter")
                                check(label + ": skip link moves keyboard focus to the heading", await page.evaluate("document.activeElement.id === 'console-main'"))
                            if width in {320, 1280}:
                                await page.screenshot(path=str(output / f"{name}-{width}-{theme}.png"), full_page=True)
                                if path == "/panels/":
                                    labels = await page.evaluate("window.gradio_config.components.filter(c => c.type === 'tabitem').map(c => c.props.label)")
                                    for title in labels:
                                        tab = page.get_by_role("tab", name=title, exact=True)
                                        menu_item = page.get_by_role("button", name=title, exact=True)
                                        if await menu_item.count() and await menu_item.is_visible():
                                            await menu_item.click()
                                        elif await tab.count() and await tab.is_visible():
                                            await tab.click()
                                        else:
                                            await page.get_by_role("button", name="More tabs", exact=True).click()
                                            await page.get_by_role("button", name=title, exact=True).click()
                                        await page.wait_for_timeout(100)
                                        inspect_result(label + " · " + title, await page.evaluate(INSPECT_JS, {"forced": False}))
                                    check(label + ": mounted console tabs inspected", len(labels) == 21, {"count": len(labels)})
                            await context.close()

                for path, name in pages:
                    context, page, errors, writes, _ = await open_page(path, 375, forced_colors="active")
                    inspect_result(name + " forced colors", await page.evaluate(INSPECT_JS, {"forced": True}))
                    check(name + " forced colors: no script errors or operational writes", not errors and not writes)
                    await context.close()

                context, page, errors, writes, state = await open_page("/c2", 320, mode="scenario")
                check("C2 mobile rail remains visible", await page.locator("#rail").is_visible())
                await page.get_by_role("button", name="Run synthetic scenario", exact=True).click()
                await page.wait_for_function("document.getElementById('chainstate').textContent.includes('LOCAL RECOMPUTE PASS')")
                check("C2 fixture renders complete recomputable chain", await page.locator("#chain [role=listitem]").count() == 2 and await page.locator("#verify").is_enabled())
                inspect_result("C2 mobile populated fixture", await page.evaluate(INSPECT_JS, {"forced": False}))
                state["mode"] = "unavailable"
                await page.get_by_role("button", name="Run synthetic scenario", exact=True).click()
                await page.wait_for_function("document.getElementById('chainstate').textContent.includes('UNAVAILABLE')")
                check("C2 unavailable result clears previous evidence", await page.locator("#chain [role=listitem]").count() == 0 and await page.locator("#verify").is_disabled())
                check("C2 fixture path makes no operational writes", not writes and not errors, {"writes": writes, "errors": errors})
                await context.close()

                context, page, errors, writes, _ = await open_page("/", 320, mode="no-library")
                check("Missing WebGL library preserves the text directory", await page.locator("#fallback").is_visible() and await page.locator(".native-estate").count() > 0)
                await page.locator("#estate-search").fill("not-a-real-estate-local-fixture")
                check("Directory empty filter has an explicit state", "No source-listed estate matches" in await page.locator("#native-estates").inner_text())
                await page.locator("#estate-search").fill("szl-skills")
                await page.get_by_text("Source and declared links", exact=True).click()
                check("Science release/candidate boundaries remain navigable", "Release artifacts do not establish a running service" in await page.locator("#native-estates").inner_text() and await page.locator("#native-estates a[href$='/pull/38']").count() == 1)
                await page.keyboard.press("Tab")
                check("Keyboard directory focus is visible", await page.evaluate("getComputedStyle(document.activeElement).outlineStyle !== 'none'"))
                check("Missing-library fallback has no uncaught script errors", not errors and not writes)
                await context.close()

                context, page, errors, writes, _ = await open_page("/", 320, mode="manifest-failed")
                check("Failed manifest never invents an estate count", "DIRECTORY UNAVAILABLE" in await page.locator("#directory-status").inner_text() and await page.locator(".native-estate").count() == 0 and await page.locator("#estate-search").is_disabled())
                check("Failed manifest has no uncaught script errors", not errors and not writes)
                await context.close()
                await browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            result = {"source": source, "checks": checks, "observations": observations, "external_requests_intercepted_locally": intercepted}
            (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    failures = [item for item in checks if not item["pass"]]
    print(json.dumps({"passed": len(checks) - len(failures), "checks": len(checks), "failed": [item["name"] for item in failures]}))
    if failures:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=7991)
    parser.add_argument("--out", type=Path, default=ROOT / "reports/native-frontdoors")
    parser.add_argument("--runtime-python", default=sys.executable)
    parser.add_argument("--browser")
    parser.add_argument("--three-root", type=Path)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--surface", choices=("all", "map", "c2", "fabric", "panels"), default="all")
    args = parser.parse_args()
    if not 1024 < args.port < 65536:
        parser.error("Port must be an unprivileged TCP port")
    if args.serve:
        serve(args.port)
    else:
        asyncio.run(qualify(args))


if __name__ == "__main__":
    main()
