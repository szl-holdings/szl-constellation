"""llm-router - the SZL Routing Command. Staged skeleton for szl-holdings/szl-router.

Doctrine v11: engines report BLOCKED when unconfigured; route admission is
ADVISORY and receipted; this plane never executes inference, never fabricates
an engine. Lambda = Conjecture 1, advisory only.
"""
import hashlib, json, math, os, time, urllib.request
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="llm-router - SZL Routing Command")
ENGINES = ["VLLM", "SGLANG", "LLAMACPP", "MLX", "TGI", "TRANSFORMERS"]
DECLARED_COST_PER_MTOK = {"llamacpp": 0.0, "mlx": 0.0, "transformers": 0.0,
                          "vllm": 0.0, "sglang": 0.0, "tgi": 0.0}  # DECLARED zero = self-host; measured pricing lands via szl-energy-attest

def _receipt(payload):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return {"sha256": hashlib.sha256(body.encode()).hexdigest(),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "signature": "UNSIGNED_HONEST"}

def engine_rows():
    rows = []
    for e in ENGINES:
        ep = os.environ.get(f"{e}_ENDPOINT")
        rows.append({"engine": e.lower(), "state": "CONFIGURED" if ep else "BLOCKED",
                     "endpoint": ep if ep else None,
                     "note": None if ep else "no endpoint configured on this host"})
    return rows

@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "llm-router", "role": "routing-command",
            "doctrine": "v11", "lambda": "Conjecture 1 (advisory)"}

@app.get("/api/router/engines")
def engines():
    return {"state": "MEASURED", "engines": engine_rows(),
            "label": "BLOCKED reported, never fabricated"}

@app.get("/api/router/models")
def models():
    try:
        req = urllib.request.Request("https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100",
                                     headers={"User-Agent": "szl-llm-router/0.1"})
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read().decode("utf-8"))
        line = [{"model": m.get("id", "").split("/")[-1], "downloads": m.get("downloads", 0),
                 "task": m.get("pipeline_tag") or "-"} for m in rows]
        line.sort(key=lambda r: -r["downloads"])
        return {"state": "MEASURED", "routable_models": line,
                "label": "MEASURED - live from the Hub API at request time"}
    except Exception as e:
        return {"state": "UNAVAILABLE", "detail": str(e)[:120],
                "label": "UNAVAILABLE - no fabricated model line"}

class RouteRequest(BaseModel):
    task: str = "text-generation"
    max_cost_per_mtok: float | None = None
    prefer: str | None = None
    context: str | None = None

@app.post("/api/router/route")
def route(req: RouteRequest):
    rows = engine_rows()
    ready = [r for r in rows if r["state"] == "CONFIGURED"]
    if not ready:
        verdict = {"admission": "BLOCKED", "detail": "no engine configured on this host - deny-by-default",
                   "considered": [r["engine"] for r in rows]}
        return {"state": "MEASURED", "verdict": verdict, "receipt": _receipt(verdict),
                "label": "MEASURED - honest BLOCKED, never a fabricated route"}
    chosen = ready[0]
    if req.prefer:
        pref = req.prefer.lower()
        match = [r for r in ready if r["engine"] == pref]
        if match:
            chosen = match[0]
    verdict = {"admission": "ADVISORY-ROUTE", "engine": chosen["engine"],
               "endpoint": chosen["endpoint"], "task": req.task,
               "cost_per_mtok_declared": DECLARED_COST_PER_MTOK.get(chosen["engine"]),
               "note": "advisory placement only - execution authority is never granted by this plane"}
    return {"state": "MEASURED", "verdict": verdict, "receipt": _receipt(verdict),
            "label": "MEASURED - placement computed from live engine state"}
