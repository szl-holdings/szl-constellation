#!/usr/bin/env python3
"""Headless, network-isolated WebGL and accessible-directory smoke of public atlas.

Only synthetic public Hub fixtures are injected. External network and all writes
are denied; this proves frontend rendering, not live Hub metadata or operations.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import subprocess
import sys
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
SPACE=ROOT/"space"
sys.path.insert(0,str(SPACE))
from atlas_public import collect

def fixture():
    def row(name,kind):
        # Fixture-only: Khipu is card-linked by Killinchu but is NOT dated
        # vertical membership. The browser must label that distinction.
        linked = kind == "space" and name == "killinchu"
        return SimpleNamespace(id="SZLHOLDINGS/"+name,private=False,sha="a"*40,
                               last_modified="2026-11-17T00:00:00Z",
                               tags=["license:apache-2.0","synthetic-render-test"],
                               sdk=("docker" if kind=="space" else None),
                               models=["SZLHOLDINGS/Khipu"] if linked else [],
                               datasets=["SZLHOLDINGS/killinchu-osint-corpus"] if linked else [])
    assets={
        "space":["killinchu","sentra","terra","lyte","counsel","finance","david-leads"],
        "model":["KILLINCHU-EYE","szl-govsign","Khipu","WILLAY"],
        "dataset":["killinchu-osint-corpus","uds-governance-receipts","szl-quant-sft-v1"],
    }
    report=collect(lister=lambda kind,limit:[row(n,kind) for n in assets[kind]],
                   topology_path=SPACE/"verticals.json")
    return report

async def main(args):
    from playwright.async_api import async_playwright
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    origin=f"http://127.0.0.1:{args.port}"
    fixture_data=fixture()
    fixture_json=json.dumps(fixture_data,sort_keys=True)
    tampered=copy.deepcopy(fixture_data)
    tampered["links"].append({
        "source":"space:SZLHOLDINGS/killinchu",
        "target":"model:SZLHOLDINGS/Khipu",
        "kind":"PUBLIC_SPACE_CARD_REFERENCES_MODEL",
        "evidence_state":"CARD_DECLARATION_NOT_EXECUTED_DEPENDENCY",
        "source_revision":"f"*40,  # forged, not the public Space revision
    })
    tampered["card_link_count"]+=1
    tampered_json=json.dumps(tampered,sort_keys=True)
    checks=[]
    def check(name,result,details=None):
        checks.append({"name":name,"pass":bool(result),"detail":details})
    env={k:os.environ[k] for k in ("PATH","SYSTEMROOT","WINDIR") if k in os.environ}
    env.update(GRADIO_ANALYTICS_ENABLED="false",HF_HUB_OFFLINE="1",PYTHONDONTWRITEBYTECODE="1")
    with (out/"server.log").open("w") as stream:
        server=subprocess.Popen([args.runtime_python,str(ROOT/"tools"/"verify_constellation_browser.py"),
                                 "--serve","--port",str(args.port)],
                                cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        try:
            ready=False
            for _ in range(160):
                if server.poll() is not None:break
                connection=HTTPConnection("127.0.0.1",args.port,timeout=2)
                try:
                    connection.request("GET","/atlas/")
                    resp=connection.getresponse()
                    resp.read()
                    if resp.status==200:
                        ready=True;break
                except OSError:
                    # The ASGI listener is still starting; use the bounded backoff below.
                    pass
                finally:connection.close()
                await asyncio.sleep(.25)
            if not ready:raise RuntimeError("ATLAS_SERVER_NOT_STARTED")
            async with async_playwright() as play:
                browser=await play.chromium.launch(headless=True,args=[
                    "--disable-dev-shm-usage","--use-gl=angle",
                    "--use-angle=swiftshader","--enable-unsafe-swiftshader"
                ])
                async def open_page(width,mode="ok",query=""):
                    context=await browser.new_context(
                        viewport={"width":width,"height":900},
                        device_scale_factor=1,reduced_motion="reduce",
                    )
                    page=await context.new_page()
                    errors=[];writes=[];off_origin=[]
                    page.on("pageerror",lambda e:errors.append(str(e)))
                    async def block_or_mock(route):
                        request=route.request
                        url=urlsplit(request.url)
                        if request.method not in {"GET","HEAD"}:
                            writes.append(request.method+" "+url.path)
                            await route.abort()
                        elif url.netloc!=f"127.0.0.1:{args.port}":
                            off_origin.append(url.hostname)
                            await route.abort()
                        elif url.path=="/api/atlas/public":
                            if mode=="ok":
                                await route.fulfill(status=200,content_type="application/json",body=fixture_json)
                            elif mode=="malicious_card":
                                await route.fulfill(status=200,content_type="application/json",body=tampered_json)
                            else:
                                await route.fulfill(status=503,content_type="application/json",
                                    body='{"schema":"szl.public-hub-holographic-atlas/v1","state":"UNAVAILABLE"}')
                        elif url.path.startswith("/api/"):
                            await route.fulfill(status=503,content_type="application/json",
                                body='{"state":"UNAVAILABLE"}')
                        else:
                            await route.continue_()
                    await context.route("**/*",block_or_mock)
                    await page.goto(origin+"/atlas/"+query,wait_until="domcontentloaded",timeout=25000)
                    return context,page,errors,writes,off_origin
                for width in (1280,375):
                    context,page,errors,writes,off_origin=await open_page(width)
                    await page.wait_for_function("document.getElementById('count-space').textContent==='7'",timeout=20000)
                    await page.wait_for_function("document.getElementById('visible-count').textContent.includes('22 visible')",timeout=20000)
                    await page.wait_for_timeout(350)
                    count=await page.locator("#viewport canvas").count()
                    rendered=count==1 and await page.locator("#viewport canvas").is_visible()
                    fallback=await page.locator("#fallback").is_visible()
                    frame=await page.evaluate("""() => { const c=document.querySelector('#viewport canvas'); return c ? {w:c.width,h:c.height,ok:!!(c.getContext('webgl2')||c.getContext('webgl'))} : null; }""")
                    check(f"{width}: real WebGL 3D canvas",rendered and not fallback and frame and frame["ok"],frame)
                    check(f"{width}: public scope counts",await page.locator("#count-model").inner_text()=="4" and await page.locator("#count-dataset").inner_text()=="3")
                    check(f"{width}: two distinct public Space-card links",await page.locator("#card-link-count").inner_text()=="2")
                    check(f"{width}: all assets listed",await page.locator("#asset-rows tr").count()==22)
                    check(f"{width}: no client error or provider write",not errors and not writes and not off_origin,
                          {"errors":errors,"writes":writes,"off_origin":off_origin})
                    overflow=await page.evaluate("document.documentElement.scrollWidth>innerWidth+2")
                    check(f"{width}: no horizontal page overflow",not overflow)
                    await page.screenshot(path=str(out/f"atlas-{width}-public-synthetic.png"),full_page=True)
                    if width==1280:
                        await page.locator("#vertical").select_option("killinchu")
                        n=int((await page.locator("#visible-count").inner_text()).split()[0])
                        check("vertical filter reduces the observed field",1<n<22,{"visible":n})
                        await page.locator("#search").fill("not-a-public-asset-123")
                        check("search does not fabricate matches",await page.locator("#asset-rows tr").count()==1
                              and "No matching" in await page.locator("#asset-rows").inner_text())
                    await context.close()
                context,page,errors,writes,off_origin=await open_page(
                    1280,query="?space=SZLHOLDINGS/killinchu")
                await page.wait_for_function("document.getElementById('selected-name').textContent==='killinchu'",timeout=20000)
                check("each public Space has a deep-link inspector",await page.locator("#open-asset").get_attribute("href")==
                      "https://huggingface.co/spaces/SZLHOLDINGS/killinchu")
                check("Space inspector exposes exact public card-referenced assets",
                      await page.locator("#linked-assets button").count()==2)
                await page.get_by_role("button",name="→ [MODEL] Khipu").click()
                await page.wait_for_function("document.getElementById('selected-name').textContent==='Khipu'",timeout=20000)
                check("Space-card model opens source-bound Khipu inspector",
                      await page.locator("#selected-name").inner_text()=="Khipu")
                await context.close()
                context,page,errors,writes,off_origin=await open_page(1280,mode="unavailable")
                await page.wait_for_function("document.getElementById('status').textContent.includes('UNAVAILABLE')",timeout=20000)
                check("unavailable API leaves no stale graph or claims",await page.locator("#viewport canvas").count()==0
                      and await page.locator("#fallback").is_visible()
                      and "Live public directory unavailable" in await page.locator("#asset-rows").inner_text())
                await context.close()
                context,page,errors,writes,off_origin=await open_page(1280,mode="malicious_card")
                await page.wait_for_function("document.getElementById('status').textContent.includes('UNAVAILABLE')",timeout=20000)
                check("forged Space-card source revision fails closed",
                      await page.locator("#viewport canvas").count()==0
                      and await page.locator("#fallback").is_visible()
                      and not errors and not writes and not off_origin)
                await context.close()
                await browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill();server.wait(timeout=5)
    result={"schema":"szl.atlas-browser-fixture-proof/v1",
            "scope":"SYNTHETIC_LOCAL_BROWSER_RENDER_ONLY",
            "checks":checks,
            "external_network_requests":0,"provider_mutations":0,
            "no_execution_authority":True}
    (out/"results.json").write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
    failures=[c for c in checks if not c["pass"]]
    print(json.dumps({"checks":len(checks),"passed":len(checks)-len(failures),
                      "failed":[c["name"] for c in failures]}))
    if failures:raise SystemExit(1)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-python",default=sys.executable)
    parser.add_argument("--port",type=int,default=7993)
    parser.add_argument("--out",type=Path,default=ROOT/"reports"/"public-atlas")
    args=parser.parse_args()
    if not 1024<args.port<65536:parser.error("invalid unprivileged port")
    asyncio.run(main(args))
