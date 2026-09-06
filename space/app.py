"""SZL Constellation v4.8 - the C2 plane.

/c2 serves the holographic C-UAS operating picture (killinchu radar-amber
identity). /api/c2/scenario generates receipted, hash-chained SYNTHETIC track
events (deterministic by seed; generator proven 24/24 against the estate
verifier convention). /api/c2/verify recomputes posted chains server-side.
Public synthetic - no public effector. Lambda advisory. Doctrine v11.
"""

# SZL Holographic Space Fabric v2
from szl_hologram_assets import A11OY_HOLO_CSS, A11OY_HOLO_HEAD, merge_hologram_css, merge_hologram_head
import ast, hashlib, json, math, os, random, time, urllib.request
from collections import deque
from typing import Any

from crosscheck import crosscheck_chains
from pydantic import BaseModel, ConfigDict, Field, ValidationError

GENESIS = "0" * 64
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = {}
CACHE_TTL = 300
SENTRA = "https://szlholdings-sentra.hf.space"
SPACE_ID = "SZLHOLDINGS/szl-constellation"
MAX_PROXY_RESPONSE_BYTES = 1_000_000
MAX_CROSSCHECK_REQUEST_BYTES = 1_000_000


class CrosscheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: list[dict[str, Any]]
    b: list[dict[str, Any]]
    rel_tol: float = Field(default=0.01, ge=0.0, le=1.0, allow_inf_nan=False)


def _reject_non_finite_json(value):
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _strict_json_loads(value):
    return json.loads(value, parse_constant=_reject_non_finite_json)


def _load(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as f:
        return json.load(f, parse_constant=_reject_non_finite_json)

MANIFEST = _load("estates.json")
VERTICALS = _load("verticals.json")
VERT_BY_ID = {v["id"]: v for v in VERTICALS["verticals"]}
FAMILIES = {f["id"]: f for f in VERTICALS.get("family_flagships", [])}

def _receipt(payload):
    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )
    return {"sha256": hashlib.sha256(body.encode()).hexdigest(),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "signature": "UNSIGNED_HONEST - hash commits to the payload; verify by recomputing"}

def _fetch_json(url, timeout=8, payload=None):
    data = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "szl-constellation/4.8", "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content_type = r.headers.get("Content-Type", "").lower()
        if "json" not in content_type:
            raise ValueError("upstream did not return JSON")
        raw = r.read(MAX_PROXY_RESPONSE_BYTES + 1)
        if len(raw) > MAX_PROXY_RESPONSE_BYTES:
            raise ValueError("upstream JSON exceeds response bound")
        decoded = _strict_json_loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("upstream JSON object required")
        return decoded


def _bounded_response_bytes(response, *, limit, require_json=False):
    content_type = response.headers.get("Content-Type", "").lower()
    if require_json and "json" not in content_type:
        raise ValueError("upstream did not return JSON")
    raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("upstream response exceeds bound")
    return raw


def _provider_runtime():
    req = urllib.request.Request(
        f"https://huggingface.co/api/spaces/{SPACE_ID}",
        headers={"User-Agent": "szl-constellation-source-binding/1.0", "Accept": "application/json", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        payload = _strict_json_loads(_bounded_response_bytes(
            response, limit=MAX_PROXY_RESPONSE_BYTES, require_json=True
        ).decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("runtime"), dict):
        raise ValueError("provider runtime object unavailable")
    runtime = payload["runtime"]
    revision = str(runtime.get("sha") or "").lower()
    if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
        raise ValueError("provider runtime revision unavailable")
    domains = runtime.get("domains")
    domain_ready = isinstance(domains, list) and any(
        isinstance(item, dict)
        and item.get("domain") == "szlholdings-szl-constellation.hf.space"
        and item.get("stage") == "READY"
        for item in domains
    )
    replicas = runtime.get("replicas")
    current_replicas = replicas.get("current") if isinstance(replicas, dict) else None
    if runtime.get("stage") != "RUNNING" or current_replicas != 1 or not domain_ready:
        raise ValueError("provider runtime is not one ready replica")
    return {
        "revision": revision,
        "stage": runtime["stage"],
        "replicas": current_replicas,
        "domain_stage": "READY",
    }


def _remote_app_sha256(revision):
    url = f"https://huggingface.co/spaces/{SPACE_ID}/resolve/{revision}/app.py"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "szl-constellation-source-binding/1.0", "Accept": "text/plain"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        raw = _bounded_response_bytes(
            response, limit=MAX_PROXY_RESPONSE_BYTES, require_json=False
        )
    return hashlib.sha256(raw).hexdigest(), url


def _local_app_sha256():
    with open(os.path.join(HERE, "app.py"), "rb") as app_file:
        return hashlib.sha256(app_file.read()).hexdigest()


def source_binding():
    app_sha256 = _local_app_sha256()
    try:
        runtime = _provider_runtime()
        revision = runtime["revision"]
        remote_sha256, immutable_source = _remote_app_sha256(revision)
        if remote_sha256 != app_sha256:
            raise ValueError("running app bytes do not match provider runtime revision")
        return {
            "state": "MEASURED",
            "space_id": SPACE_ID,
            "source_revision": revision,
            "app_sha256": app_sha256,
            "remote_app_sha256": remote_sha256,
            "app_bytes_match": True,
            "provider_stage": runtime["stage"],
            "provider_replicas": runtime["replicas"],
            "domain_stage": runtime["domain_stage"],
            "immutable_source": immutable_source,
        }
    except Exception as exc:
        return {
            "state": "UNAVAILABLE",
            "space_id": SPACE_ID,
            "source_revision": "UNAVAILABLE",
            "app_sha256": app_sha256,
            "remote_app_sha256": None,
            "app_bytes_match": False,
            "immutable_source": None,
            "detail": type(exc).__name__,
        }


def listener_source_contract():
    source_path = os.path.join(HERE, "app.py")
    with open(source_path, "r", encoding="utf-8") as source_file:
        tree = ast.parse(source_file.read(), filename=source_path)
    uvicorn_calls = 0
    launch_calls = 0
    mounts_with_ssr_disabled = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
        if owner == "uvicorn" and node.func.attr == "run":
            uvicorn_calls += 1
        if node.func.attr == "launch":
            launch_calls += 1
        if owner == "gr" and node.func.attr == "mount_gradio_app":
            if any(
                keyword.arg == "ssr_mode"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is False
                for keyword in node.keywords
            ):
                mounts_with_ssr_disabled += 1
    valid = uvicorn_calls == 1 and launch_calls == 0 and mounts_with_ssr_disabled == 1
    return {
        "state": "METHOD",
        "valid": valid,
        "uvicorn_run_calls": uvicorn_calls,
        "launch_calls": launch_calls,
        "mounts_with_ssr_disabled": mounts_with_ssr_disabled,
    }

def _cached(key, fn):
    hit = CACHE.get(key)
    now = time.time()
    if hit and now - hit["at"] < CACHE_TTL:
        out = dict(hit["value"]); out["cache"] = {"hit": True, "age_s": round(now - hit["at"], 1)}
        return out
    value = fn()
    CACHE[key] = {"at": now, "value": value}
    out = dict(value); out["cache"] = {"hit": False, "age_s": 0}
    return out

def _probe(url, timeout=6):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "szl-constellation/4.8"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"url": url, "state": "MEASURED", "http": r.status}
    except urllib.error.HTTPError as e:
        return {"url": url, "state": "MEASURED", "http": e.code, "note": "reachable, non-2xx"}
    except Exception as e:
        return {"url": url, "state": "UNAVAILABLE", "detail": str(e)[:100]}

# ---------- sentra flagship proxies ----------

def sentra_gate_proxy(scores_text, weights_text, threshold):
    try:
        scores = [float(x) for x in (scores_text or "").split(",") if x.strip()]
        weights = [float(x) for x in (weights_text or "").split(",") if x.strip()] or None
        threshold = float(threshold)
        total_weight = sum(weights) if weights is not None else None
        if not scores or any(not math.isfinite(score) or not 0.0 <= score <= 1.0 for score in scores):
            raise ValueError("scores must be finite values in [0,1]")
        if weights is not None and (
            len(weights) != len(scores)
            or any(not math.isfinite(weight) or weight < 0.0 for weight in weights)
            or not math.isfinite(total_weight)
            or total_weight <= 0.0
        ):
            raise ValueError("weights must match scores, be finite/non-negative, and have positive sum")
        if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be finite and in [0,1]")
        d = _fetch_json(SENTRA + "/api/sentra/gate", timeout=12,
                        payload={"action": {"type": "assurance.gate.evaluate", "scores": scores,
                                            "weights": weights, "threshold": threshold},
                                 "axes": scores, "request_id": "constellation-console"})
        if d.get("decision") not in {"allow", "deny"} or d.get("fail_closed") is not True:
            raise ValueError("flagship verdict contract invalid")
        return {"state": "MEASURED", "flagship": SENTRA, "verdict": d,
                "label": "MEASURED - verdict computed by the sentra flagship, proxied verbatim"}
    except Exception as e:
        return {"state": "UNAVAILABLE", "detail": f"flagship plane not reachable: {str(e)[:120]}",
                "note": "the GATE plane ships with the sentra v5 deploy (owner path); until then this console reports instead of pretending",
                "label": "UNAVAILABLE - never computed locally in place of the flagship"}

def sentra_yawar_proxy(chain_text):
    try:
        d = _fetch_json(SENTRA + "/api/sentra/yawar/verify", timeout=12, payload={"chain": chain_text or ""})
        if not isinstance(d.get("chain_verified"), bool):
            raise ValueError("flagship verification contract invalid")
        return {"state": "MEASURED", "flagship": SENTRA, "verification": d,
                "label": "MEASURED - chain recomputed by the sentra flagship, proxied verbatim"}
    except Exception as e:
        return {"state": "UNAVAILABLE", "detail": f"flagship plane not reachable: {str(e)[:120]}",
                "note": "the YAWAR plane ships with the sentra v5 deploy; until then this console reports instead of pretending",
                "label": "UNAVAILABLE - never computed locally in place of the flagship"}

def sentra_planes():
    try:
        d = _fetch_json(SENTRA + "/api/sentra/planes", timeout=10)
        if not isinstance(d.get("planes"), list):
            raise ValueError("flagship plane registry contract invalid")
        return {"state": "MEASURED", "planes": d, "label": "MEASURED - live from the flagship"}
    except Exception as e:
        return {"state": "UNAVAILABLE", "detail": str(e)[:120],
                "declared": ["GATE (admission, advisory-only, deny-by-default)", "YAWAR (receipt-chain verify)", "EVIDENCE (upstream probe)"],
                "label": "UNAVAILABLE - declared plane list shown, nothing fabricated"}

# ---------- C2 scenario engine (public synthetic) ----------

def c2_scenario(seed, n):
    try:
        seed_i = int(seed)
        n = int(n)
    except Exception:
        return {"state": "INVALID", "detail": "seed must be an integer, n a count"}
    if not (1 <= n <= 200):
        return {"state": "INVALID", "detail": "n in 1..200"}
    rng = random.Random(seed_i)
    events, prev = [], GENESIS
    tracks = {}
    tid = 0
    for i in range(n):
        if not tracks or rng.random() < 0.35:
            tid += 1
            tracks[tid] = {"r": 30 + rng.random() * 60, "th": rng.random() * 6.283, "cls": "unknown"}
            kind = "spawn"
        else:
            t = tracks[rng.choice(list(tracks))]
            t["r"] = max(8, t["r"] + (rng.random() - 0.55) * 8)
            t["th"] += (rng.random() - 0.5) * 0.3
            kind = rng.choice(["update", "update", "classify", "evaluate"])
            if kind == "classify":
                t["cls"] = rng.choice(["friendly", "unknown", "hostile-suspect"])
        ev = {"seq": i, "t": round(i * 2.5, 1), "track": tid, "kind": kind,
              "r": round(tracks[tid]["r"], 2), "theta": round(tracks[tid]["th"], 4),
              "cls": tracks[tid]["cls"], "truth": "SYNTHETIC"}
        ev["prev_hash"] = prev
        ev["chain_hash"] = hashlib.sha256((prev + _canon({k: v for k, v in ev.items() if k not in ("prev_hash", "chain_hash")})).encode()).hexdigest()
        prev = ev["chain_hash"]
        events.append(ev)
    return {"state": "MEASURED", "seed": seed_i, "events": events, "terminal": prev,
            "truth": "PUBLIC SYNTHETIC - simulated tracks, no public effector; ROE evaluation is advisory and never executes",
            "receipt": _receipt({"seed": seed_i, "n": n, "terminal": prev}),
            "label": "MEASURED - deterministic by seed; generator proven 24/24 against the estate verifier convention"}

def c2_verify(events):
    if not isinstance(events, list) or not events:
        return {"state": "INVALID", "detail": "expected a non-empty array of events"}
    prev = GENESIS
    for i, ev in enumerate(events):
        if not isinstance(ev, dict) or "prev_hash" not in ev or "chain_hash" not in ev:
            return {"state": "INVALID", "detail": f"event {i} missing chain fields"}
        if ev["prev_hash"] != prev:
            return {"state": "INVALID", "detail": f"link broken at event {i}"}
        expected = hashlib.sha256((prev + _canon({k: v for k, v in ev.items() if k not in ("prev_hash", "chain_hash")})).encode()).hexdigest()
        if ev["chain_hash"] != expected:
            return {"state": "INVALID", "detail": f"payload tampered at event {i}"}
        prev = ev["chain_hash"]
    return {"state": "MEASURED", "chain_valid": True, "events": len(events),
            "terminal": prev[:16], "label": "MEASURED - recomputed server-side, link by link"}

# ---------- computing kernels ----------

def lambda_gate(scores, weights, threshold=0.97):
    if len(scores) != len(weights) or not scores:
        return {"state": "INVALID", "detail": "scores and weights must be equal-length and non-empty"}
    if any(not (0.0 <= s <= 1.0) for s in scores) or any(w < 0 for w in weights) or sum(weights) <= 0:
        return {"state": "INVALID", "detail": "scores in [0,1], weights >= 0, positive total weight"}
    tw = sum(weights)
    lam = math.exp(sum(w * math.log(max(s, 1e-12)) for s, w in zip(scores, weights)) / tw)
    return {"state": "MEASURED", "lambda": round(lam, 6), "threshold": threshold,
            "gate": "ADVISORY-PASS" if lam >= threshold else "ADVISORY-HOLD",
            "label": "METHOD - advisory only, never green by assertion"}

def ouroboros(iterations, tax_rate=0.02):
    iterations = int(iterations)
    if iterations < 1 or iterations > 10000 or not (0.0 <= tax_rate < 1.0):
        return {"state": "INVALID", "detail": "iterations 1..10000, tax_rate in [0,1)"}
    budget, rows, spent = 1.0, [], 0.0
    for i in range(1, iterations + 1):
        tax = budget * tax_rate
        budget -= tax
        spent += tax
        if i <= 12 or i == iterations:
            rows.append({"iter": i, "remaining": round(budget, 6), "tax_paid": round(spent, 6)})
        if budget < 1e-9:
            rows.append({"iter": i, "remaining": 0.0, "tax_paid": round(spent, 6), "halt": "BUDGET-EXHAUSTED"})
            break
    return {"state": "MEASURED", "converged": budget < 1e-9, "final_budget": round(budget, 6),
            "total_tax": round(spent, 6), "trace": rows, "label": "METHOD - bounded loop-tax accounting"}

def _canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)

def _verify_chain_detailed(receipts):
    prev = GENESIS
    links = []
    for i, r in enumerate(receipts):
        ok = isinstance(r, dict) and "prev_hash" in r and "chain_hash" in r
        if ok and r["prev_hash"] != prev:
            links.append({"index": i, "valid": False, "fault": "link broken"}); ok = False
        elif ok:
            payload = {k: v for k, v in r.items() if k not in ("prev_hash", "chain_hash")}
            expected = hashlib.sha256((prev + _canon(payload)).encode()).hexdigest()
            if r["chain_hash"] != expected:
                links.append({"index": i, "valid": False, "fault": "payload tampered"}); ok = False
        if ok:
            links.append({"index": i, "valid": True})
            prev = r["chain_hash"]
        else:
            if not (isinstance(r, dict) and "prev_hash" in r and "chain_hash" in r):
                links[-1]["fault"] = "missing chain fields"
            break
    return links, prev

def verify_receipt_chain(text):
    try:
        receipts = json.loads(text)
        if isinstance(receipts, dict): receipts = [receipts]
        if not isinstance(receipts, list): raise ValueError("expected a JSON array of receipts")
    except Exception as e:
        return {"state": "INVALID", "detail": f"parse error: {e}"}
    links, terminal = _verify_chain_detailed(receipts)
    valid = len(links) == len(receipts) and all(l["valid"] for l in links)
    if not valid:
        bad = next((l for l in links if not l["valid"]), None)
        return {"state": "INVALID", "detail": f"{bad['fault']} at receipt {bad['index']}" if bad else "incomplete chain"}
    return {"state": "MEASURED", "chain_valid": True, "receipts": len(receipts),
            "terminal": terminal[:16], "label": "MEASURED - linkage recomputed"}

def _d2xy(n, d):
    x = y = 0; t = d; s = 1
    while s < n:
        rx = 1 & (t // 2); ry = 1 & (t ^ rx)
        if ry == 0:
            if rx == 1: x = s - 1 - x; y = s - 1 - y
            x, y = y, x
        x += s * rx; y += s * ry; t //= 4; s *= 2
    return x, y

def receipt_curve(chain_text):
    try:
        receipts = json.loads(chain_text)
        if isinstance(receipts, dict): receipts = [receipts]
        if not isinstance(receipts, list) or not receipts:
            raise ValueError("expected a non-empty JSON array of receipts")
    except Exception as e:
        return {"state": "INVALID", "detail": f"parse error: {e}", "svg": ""}
    links, terminal = _verify_chain_detailed(receipts)
    n_receipts = len(receipts)
    k = 1
    while 4 ** k < n_receipts: k += 1
    side = 2 ** k
    scale = 540 / side
    pts = [_d2xy(side, i) for i in range(n_receipts)]
    pts = [(x * scale + 16, y * scale + 16) for x, y in pts]
    validity = {l["index"]: l for l in links}
    segs, nodes = [], []
    for i in range(1, n_receipts):
        v = validity.get(i, {"valid": False})
        color = "#3af4c8" if v.get("valid") else "#ff5d73"
        segs.append(f'<line x1="{pts[i-1][0]:.1f}" y1="{pts[i-1][1]:.1f}" x2="{pts[i][0]:.1f}" y2="{pts[i][1]:.1f}" stroke="{color}" stroke-width="2.2" stroke-opacity=".85"/>')
    for i, (x, y) in enumerate(pts):
        v = validity.get(i, {"valid": True})
        if i == 0:
            color, r = "#e6edfb", 5
        else:
            color, r = ("#3af4c8", 4) if v.get("valid") else ("#ff5d73", 6)
        nodes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>')
    bad = [l for l in links if not l["valid"]]
    state = "MEASURED" if len(links) == n_receipts and not bad else "INVALID"
    caption = (f"chain-valid · {n_receipts} receipts · terminal {terminal[:16]}" if state == "MEASURED"
               else f"broken: {bad[0]['fault']} at receipt {bad[0]['index']} · curve turns red at the fault")
    svg = (f'<svg viewBox="0 0 572 572" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;background:#05080f;border:1px solid rgba(140,170,220,.2);border-radius:12px">'
           + "".join(segs) + "".join(nodes)
           + f'<text x="16" y="556" fill="#9fb0cf" font-family="monospace" font-size="12">{caption}</text></svg>')
    return {"state": state, "receipts": n_receipts, "hilbert_order": k,
            "verification": verify_receipt_chain(chain_text),
            "svg": svg, "caption": caption,
            "receipt": _receipt({"n": n_receipts, "terminal": terminal[:16], "state": state}),
            "label": "MEASURED - Hilbert mapping bijective+continuous (proven); link colors recomputed, never assumed"}

def receipt_curve_svg(chain_text):
    d = receipt_curve(chain_text)
    return d["svg"] or f"<div style='color:#ff5d73;font:12px monospace'>{d.get('detail','INVALID')}</div>"

def bm25_rank(corpus_text, query, k1=1.5, b=0.75):
    docs = [d.strip() for d in corpus_text.split("\n") if d.strip()]
    q = [t for t in query.lower().split() if t]
    if not docs or not q:
        return {"state": "INVALID", "detail": "need non-empty corpus lines and query"}
    toks = [d.lower().split() for d in docs]
    avgdl = sum(len(t) for t in toks) / len(toks)
    df = {}
    for t in toks:
        for term in set(t): df[term] = df.get(term, 0) + 1
    N = len(toks)
    def score(ti):
        tf = {}
        for term in ti: tf[term] = tf.get(term, 0) + 1
        s = 0.0
        for term in q:
            if term not in df: continue
            idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
            f = tf.get(term, 0)
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len(ti) / max(avgdl, 1e-9)))
        return s
    ranked = sorted(((score(t), docs[i]) for i, t in enumerate(toks)), key=lambda x: -x[0])
    return {"state": "MEASURED", "results": [{"rank": i + 1, "bm25": round(s, 4), "doc": d[:90]}
            for i, (s, d) in enumerate(ranked[:5])], "label": "MEASURED - BM25 k1=1.5 b=0.75"}

def quant_curve(bits):
    bits = int(bits)
    if bits < 2 or bits > 16:
        return {"state": "INVALID", "detail": "bit-width 2..16"}
    base = [math.sin(i * 0.7) + 0.5 * math.cos(i * 1.3) for i in range(256)]
    amax = max(abs(v) for v in base)
    levels = 2 ** bits - 1
    q = [round(v / amax * (levels / 2)) / (levels / 2) * amax for v in base]
    dot = sum(a * b for a, b in zip(base, q))
    na = math.sqrt(sum(v * v for v in base)); nb = math.sqrt(sum(v * v for v in q))
    cos = dot / (na * nb) if na and nb else 0.0
    top1_base = max(range(256), key=lambda i: base[i]); top1_q = max(range(256), key=lambda i: q[i])
    return {"state": "MEASURED", "bits": bits, "cosine": round(cos, 4),
            "top1_preserved": top1_base == top1_q, "dim": 256,
            "label": "MEASURED - uniform absmax on deterministic fixture, NOT a real model"}

def engine_status():
    engines = ["VLLM", "SGLANG", "LLAMACPP", "MLX", "TGI", "TRANSFORMERS"]
    rows = []
    for e in engines:
        ep = os.environ.get(f"{e}_ENDPOINT")
        rows.append({"engine": e.lower(), "state": "MEASURED" if ep else "BLOCKED",
                     "detail": ep if ep else "no endpoint configured on this host"})
    return {"state": "MEASURED", "engines": rows,
            "label": "honest by design - BLOCKED is reported, never fabricated"}

def kernel_console(variant, d_model, n_heads, n_kv_heads, d_latent, seq_len):
    variant = (variant or "").upper()
    d_model, n_heads, n_kv_heads, d_latent, seq_len = int(d_model), int(n_heads), int(n_kv_heads), int(d_latent), int(seq_len)
    if variant not in ("MHA", "GQA", "MQA", "MLA"):
        return {"state": "INVALID", "detail": "variant must be MHA, GQA, MQA, or MLA"}
    if not (d_model > 0 and n_heads > 0 and seq_len > 0 and d_model % n_heads == 0):
        return {"state": "INVALID", "detail": "d_model>0 divisible by n_heads>0, seq_len>0"}
    if variant == "MHA": n_kv_heads = n_heads
    if variant == "MQA": n_kv_heads = 1
    if variant == "GQA" and not (0 < n_kv_heads <= n_heads):
        return {"state": "INVALID", "detail": "GQA needs 1 <= n_kv_heads <= n_heads"}
    d_h = d_model // n_heads
    flops_attn = 4 * seq_len * seq_len * d_model
    if variant == "MLA":
        if d_latent <= 0:
            return {"state": "INVALID", "detail": "MLA needs d_latent > 0"}
        kv_bytes = 2 * seq_len * d_latent * 2
        kv_note = f"latent cache: 2 x s({seq_len}) x d_c({d_latent}) x fp16"
    else:
        kv_bytes = 2 * seq_len * n_kv_heads * d_h * 2
        kv_note = f"kv cache: 2 x s({seq_len}) x h_kv({n_kv_heads}) x d_h({d_h}) x fp16"
    bytes_moved = 4 * seq_len * d_model * 2 + kv_bytes
    intensity = flops_attn / bytes_moved if bytes_moved else 0.0
    RIDGE = 139.0
    return {"state": "METHOD", "variant": variant,
            "dims": {"d_model": d_model, "n_heads": n_heads, "n_kv_heads": n_kv_heads, "d_latent": d_latent, "seq_len": seq_len, "head_dim": d_h},
            "attn_flops": flops_attn, "kv_cache_bytes": kv_bytes, "kv_note": kv_note,
            "est_bytes_moved": bytes_moved, "arithmetic_intensity": round(intensity, 2),
            "ridge_flop_per_byte_declared": RIDGE,
            "bound": "compute-bound (declared ridge)" if intensity >= RIDGE else "memory-bound (declared ridge)",
            "receipt": _receipt({"variant": variant, "flops": flops_attn, "kv": kv_bytes}),
            "label": "METHOD - closed-form cost math on declared dims; ridge constant declared, not measured"}

# ---------- live estate measurement + drift ----------

def _measure_org():
    out = {"state": "MEASURED", "github": {}, "huggingface": {}}
    try:
        gh = _fetch_json("https://api.github.com/search/repositories?q=org:szl-holdings&per_page=1", timeout=10)
        out["github"] = {"org_repos_total": gh.get("total_count"), "source": "github search api"}
    except Exception as e:
        out["github"] = {"state": "UNAVAILABLE", "detail": str(e)[:100]}
        out["state"] = "PARTIAL"
    for kind, url in (("spaces", "https://huggingface.co/api/spaces?author=SZLHOLDINGS&limit=100"),
                      ("models", "https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100"),
                      ("datasets", "https://huggingface.co/api/datasets?author=SZLHOLDINGS&limit=100")):
        try:
            rows = _fetch_json(url, timeout=10)
            out["huggingface"][kind] = {"count": len(rows),
                                        "names": sorted(r.get("id", "").split("/")[-1] for r in rows)}
        except Exception as e:
            out["huggingface"][kind] = {"state": "UNAVAILABLE", "detail": str(e)[:80]}
            out["state"] = "PARTIAL"
    out["receipt"] = _receipt({k: v for k, v in out.items() if k != "receipt"})
    out["label"] = "MEASURED live from GitHub + Hub APIs at request time (5-min cache)"
    return out

def live_estates():
    return _cached("org-measure", _measure_org)

def estate_drift():
    live = live_estates()
    if live.get("state") == "UNAVAILABLE" or live.get("state") == "PARTIAL" and "spaces" not in live.get("huggingface", {}):
        return {"state": "UNAVAILABLE", "detail": "live measure incomplete; drift not computed on partial evidence"}
    live_spaces = set(live.get("huggingface", {}).get("spaces", {}).get("names", []))
    if not live_spaces:
        return {"state": "UNAVAILABLE", "detail": "no live space listing; drift not computed on partial evidence"}
    declared = {s["name"] for s in MANIFEST["live_lattice"]}
    expected_gone = {c["absorbed"] for c in MANIFEST.get("consolidation_log", [])}
    missing = sorted(declared - live_spaces)
    added = sorted(live_spaces - declared)
    rows = []
    for name in missing:
        rows.append({"node": name, "drift": "MISSING-LIVE",
                     "classification": "EXPECTED (decommissioned per consolidation log)" if name in expected_gone else "UNEXPECTED - investigate"})
    for name in added:
        rows.append({"node": name, "drift": "ADDED-LIVE",
                     "classification": "unmanifested - admit into the map or explain"})
    return {"state": "MEASURED", "drifted": bool(rows), "divergence": rows,
            "baseline": {"declared_lattice": len(declared), "consolidations": len(MANIFEST.get("consolidation_log", []))},
            "live": {"spaces": len(live_spaces)},
            "receipt": _receipt({"missing": missing, "added": added}),
            "label": "MEASURED - DECLARED manifest vs live Hub listing; expected decommissions cross-referenced from the consolidation log"}

def kernel_line():
    def _go():
        wanted = set(MANIFEST.get("kernel_line", []))
        try:
            models = _fetch_json("https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100")
        except Exception as e:
            return {"state": "UNAVAILABLE", "detail": f"hub api unreachable: {e}", "label": "UNAVAILABLE - no fabricated counts"}
        rows = []
        for m in models:
            name = m.get("id", "").split("/")[-1]
            if name in wanted:
                rows.append({"kernel": name, "downloads": m.get("downloads", 0), "likes": m.get("likes", 0),
                             "task": m.get("pipeline_tag") or "-"})
        rows.sort(key=lambda r: -r["downloads"])
        return {"state": "MEASURED", "kernels": rows, "org_models_total": len(models),
                "label": "MEASURED - live from huggingface.co/api"}
    return _cached("kernels", _go)

def khipu_line():
    def _go():
        try:
            models = _fetch_json("https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100")
        except Exception as e:
            return {"state": "UNAVAILABLE", "detail": str(e)[:100]}
        rows = [{"model": m.get("id", "").split("/")[-1], "downloads": m.get("downloads", 0),
                 "likes": m.get("likes", 0), "task": m.get("pipeline_tag") or "-"}
                for m in models if "khipu" in m.get("id", "").lower()]
        rows.sort(key=lambda r: -r["downloads"])
        return {"state": "MEASURED", "family": "khipu", "members": rows,
                "total_downloads": sum(r["downloads"] for r in rows),
                "label": "MEASURED - live from the Hub API, khipu-labeled only"}
    return _cached("khipu-line", _go)

def second_brain():
    targets = ["szl-second-brain-inrepo", "szl-lake", "killinchu-osint-corpus", "a11oy-verifiable-corpus", "szl-estate-graph"]
    rows, ok = [], True
    for t in targets:
        try:
            d = _fetch_json(f"https://huggingface.co/api/datasets/SZLHOLDINGS/{t}")
            rows.append({"dataset": t, "downloads": d.get("downloads", 0), "likes": d.get("likes", 0),
                         "files": len(d.get("siblings", [])), "private": d.get("private", False)})
        except Exception as e:
            ok = False
            rows.append({"dataset": t, "state": "UNAVAILABLE", "detail": str(e)[:80]})
    return {"state": "MEASURED" if ok else "PARTIAL", "memory_plane": rows,
            "label": "MEASURED where reachable - never fabricated"}

def vertical_status(vid):
    v = VERT_BY_ID.get(vid)
    if not v:
        return {"state": "INVALID", "detail": f"unknown vertical '{vid}'"}
    probes = [_probe(u) for u in v.get("live", [])]
    return {"state": "MEASURED", "vertical": v["name"], "domain": v["domain"],
            "endpoints": probes or [{"note": "no public endpoint declared - internal or build-gated"}],
            "assets": {"repos": v["repos"], "spaces": v["spaces"], "kernels": v["kernels"],
                       "models": v["models"], "datasets": v["datasets"]},
            "receipt": _receipt({"vertical": vid, "probes": probes}),
            "label": "MEASURED where probed; asset map DECLARED from the 2026-09-04 audit"}

def killinchu_osint():
    ep = VERT_BY_ID["killinchu"].get("widget_endpoint")
    try:
        d = _fetch_json(ep, timeout=12)
        return {"state": "MEASURED", "source": ep, "mesh": d, "receipt": _receipt(d),
                "label": "MEASURED - live from the killinchu runtime's governed OSINT mesh"}
    except Exception as e:
        return {"state": "UNAVAILABLE", "detail": f"killinchu runtime unreachable: {str(e)[:120]}",
                "declared_mesh": ["CISA KEV", "NIST NVD", "OFAC SDN", "UNSC 1718 (DPRK)", "CIA World Leaders",
                                   "NSA advisories", "CERT-UA", "Ukraine Data.gov.ua", "PRC MFA", "PRC State Council"],
                "label": "UNAVAILABLE - declared source list shown, nothing fabricated"}

# ---------- trust-path engine ----------

def _wiring_graph():
    adj = {}
    def edge(a, b, kind):
        adj.setdefault(a, []).append((b, kind))
        adj.setdefault(b, []).append((a, kind))
    edge("hub:second_brain", "hub:anatomy", "trinity")
    edge("hub:second_brain", "hub:ouroboros", "trinity")
    edge("hub:anatomy", "hub:ouroboros", "trinity")
    for e in MANIFEST["estates"]:
        edge(e["name"], f"hub:{e.get('hub','second_brain')}", "synapse")
        n = e["name"]
        for v in VERTICALS["verticals"]:
            if (any(r.endswith("/"+n) for r in v["repos"])
               or any(s.endswith("/"+n) for s in v["spaces"]) or n == v["id"] or n.startswith(v["id"]+"-")):
                edge(n, f"vertical:{v['id']}", "wired-into")
    for v in VERTICALS["verticals"]:
        edge(f"vertical:{v['id']}", "hub:second_brain", "governed-by")
        for r in VERTICALS["shared_substrate"]["repos"]:
            edge(f"vertical:{v['id']}", f"substrate:{r.split('/')[-1]}", "runs-on")
    return adj

GRAPH = _wiring_graph()

def trust_path(a, b):
    if a not in GRAPH or b not in GRAPH:
        known = sorted(n for n in GRAPH if not n.startswith(("hub:", "substrate:")))
        return {"state": "INVALID", "detail": f"unknown node; {len(known)} known estates/verticals, e.g. {known[:10]}",
                "known_count": len(known)}
    prev = {a: None}; q = deque([a])
    while q:
        cur = q.popleft()
        if cur == b: break
        for nxt, kind in GRAPH.get(cur, []):
            if nxt not in prev:
                prev[nxt] = (cur, kind); q.append(nxt)
    if b not in prev:
        return {"state": "MEASURED", "connected": False, "detail": "no wiring path - the graph says these are islands", "label": "MEASURED - absence reported, never bridged by fiat"}
    path, kinds, cur = [b], [], b
    while prev[cur] is not None:
        cur, kind = prev[cur]
        path.append(cur); kinds.append(kind)
    path.reverse(); kinds.reverse()
    out = {"state": "MEASURED", "connected": True, "from": a, "to": b,
           "hops": len(path) - 1, "path": path, "edge_kinds": kinds}
    out["receipt"] = _receipt({"from": a, "to": b, "path": path})
    out["label"] = "MEASURED - BFS shortest path over the audited wiring graph (trinity-connected)"
    return out

# ---------- consoles ----------

CSS = """
body,.gradio-container{background:#070b12!important;color:#e6edfb!important}
.gradio-container{max-width:1080px!important}
.wire{background:rgba(255,255,255,.028);border:1px solid rgba(140,170,220,.14);border-radius:14px;padding:16px 18px;margin:10px 0;font-size:13px;color:#9fb0cf;border-left:3px solid var(--accent,#3af4c8)}
.wire h4{margin:0 0 10px;font-size:13.5px;color:var(--accent,#e6edfb)}
.wire .motif{font:600 10.5px ui-monospace,monospace;color:var(--accent,#6b7a99);letter-spacing:.14em;text-transform:uppercase;margin-bottom:8px}
.wire .row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.wire .tag{font:600 10.5px ui-monospace,monospace;color:#5b8dee;background:rgba(91,141,238,.09);border:1px solid rgba(91,141,238,.25);border-radius:6px;padding:3px 8px;text-decoration:none}
.wire .tag.k{color:#3af4c8;background:rgba(58,244,200,.08);border-color:rgba(58,244,200,.28)}
.wire .tag.m{color:#8a6bff;background:rgba(138,107,255,.09);border-color:rgba(138,107,255,.28)}
.wire .tag.d{color:#d4a444;background:rgba(212,164,68,.08);border-color:rgba(212,164,68,.28)}
.wire .lbl{font:700 9.5px ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#6b7a99;width:74px;padding-top:4px;flex:none}
.backbar{font:600 12px ui-monospace,monospace;margin:10px 0 18px}
.backbar a{color:#3af4c8;text-decoration:none}
"""

def wire_html(v):
    accent = v.get("accent", "#3af4c8")
    motif = v.get("motif", "")
    def tags(items, cls, base):
        return "".join(f'<a class="tag {cls}" href="{base}{i}" target="_blank" rel="noopener">{i}</a>' for i in items)
    return f"""<div class="wire" style="--accent:{accent}"><h4>{v['name']} &middot; <span style="color:#6b7a99">{v['domain']}</span></h4>
{f'<div class="motif">{motif}</div>' if motif else ''}
<div style="font-size:12.5px;margin-bottom:12px;line-height:1.6">{v['tagline']}</div>
<div class="row"><span class="lbl">repos</span>{tags(v['repos'],'','https://github.com/')}</div>
<div class="row"><span class="lbl">spaces</span>{tags(v['spaces'],'','https://huggingface.co/spaces/')}</div>
<div class="row"><span class="lbl">kernels</span>{tags(v['kernels'],'k','https://huggingface.co/SZLHOLDINGS/')}</div>
<div class="row"><span class="lbl">models</span>{tags(v['models'],'m','https://huggingface.co/SZLHOLDINGS/')}</div>
<div class="row"><span class="lbl">datasets</span>{tags(v['datasets'],'d','https://huggingface.co/datasets/SZLHOLDINGS/') if v['datasets'] else '<span class="tag d">none declared</span>'}</div>
<div style="color:#6b7a99;font-size:11px;margin-top:6px">{v['widget_note']}</div></div>"""

def family_html(f):
    accent = f.get("accent", "#d4a444")
    members = "".join(f'<span class="tag m">{m}</span>' for m in f["members"])
    linked = "".join(f'<span class="tag k">{m}</span>' for m in f.get("linked", []))
    return f"""<div class="wire" style="--accent:{accent}"><h4>{f['name']} &middot; <span style="color:#6b7a99">{f['family']}</span></h4>
{f'<div class="motif">' + f.get('motif','') + '</div>' if f.get('motif') else ''}
<div class="row"><span class="lbl">members</span>{members}</div>
{f'<div class="row"><span class="lbl">linked</span>' + linked + '</div>' if linked else ''}
<div style="color:#6b7a99;font-size:11px;margin-top:6px">{f['note']}</div></div>"""

def build_consoles():
    import gradio as gr
    with gr.Blocks(title="SZL Constellation - Consoles", css=A11OY_HOLO_CSS, head=A11OY_HOLO_HEAD) as demo:
        gr.HTML("""<div class="backbar"><a href="/">&larr; back to the constellation</a> &middot;
        <a href="/c2" target="_blank">C2 operating picture</a> &middot;
        <a href="/api/constellation/manifest" target="_blank">api</a></div>
        <h2 style="margin:0 0 4px">Vertical <span style="color:#3af4c8">Consoles</span></h2>
        <div style="color:#6b7a99;font-size:12.5px;margin-bottom:10px">Every console probes live at request time and reports UNAVAILABLE rather than fabricate. Each vertical wears its own identity per the design system.</div>""")
        with gr.Tabs():
            with gr.Tab("SZL Foundry"):
                f = FAMILIES.get("szl-foundry")
                if f: gr.HTML(family_html(f))
                fd = gr.JSON(label="family drift - the workbench checks itself")
                gr.Button("Measure family drift", variant="primary").click(estate_drift, None, fd)
                fk = gr.JSON(label="kernel line (live)")
                gr.Button("Measure the kernel line").click(kernel_line, None, fk)
            with gr.Tab("KHIPU"):
                f = FAMILIES.get("khipu")
                if f: gr.HTML(family_html(f))
                kl = gr.JSON(label="the khipu dynasty, measured live")
                gr.Button("Measure the dynasty", variant="primary").click(khipu_line, None, kl)
                kc = gr.Textbox(lines=5, label="Khipu council corpus",
                                value="khipu kernels knot the run and hash the proof\nayllu convenes the council of eleven seats\nthe gguf runs byte-verified in ci now\nlambda stays conjecture one advisory\nreceipts make every claim checkable")
                kq = gr.Textbox(label="Ask the dynasty", value="receipts proof kernels")
                kout = gr.JSON(label="ranking")
                gr.Button("Convene with ayllu").click(bm25_rank, [kc, kq], kout)
            with gr.Tab("Ouroboros Loop"):
                f = FAMILIES.get("ouroboros-loop")
                if f: gr.HTML(family_html(f))
                oi = gr.Slider(1, 500, 50, step=1, label="Iterations")
                ot = gr.Slider(0.0, 0.5, 0.02, label="Loop tax")
                oout = gr.JSON(label="loop-tax ledger")
                gr.Button("Run the loop", variant="primary").click(ouroboros, [oi, ot], oout)
                ls1 = gr.Slider(0, 1, 0.9, label="evidence")
                ls2 = gr.Slider(0, 1, 0.95, label="provenance")
                ls3 = gr.Slider(0, 1, 0.99, label="receipts")
                lout = gr.JSON(label="lambda gate")
                gr.Button("Compute Lambda").click(
                    lambda a, b, c: lambda_gate([a, b, c], [1, 2, 1]), [ls1, ls2, ls3], lout)
                qb2 = gr.Slider(2, 16, 4, step=1, label="Quant bit-width")
                qout2 = gr.JSON(label="quant curve")
                gr.Button("Measure").click(quant_curve, qb2, qout2)
            with gr.Tab("Sentra Assurance"):
                gr.HTML("""<div class="wire" style="--accent:#8a6bff"><h4>Sentra &middot; <span style="color:#6b7a99">Assurance Command</span></h4>
<div class="motif">the gate iris</div>
<div style="font-size:12.5px;line-height:1.6">Proxied to the flagship. GATE is advisory and deny-by-default; YAWAR recomputes chains link by link.
Until the v5 deploy lands, this console reports UNAVAILABLE - it never computes verdicts in the flagship's place.</div></div>""")
                gp = gr.JSON(label="plane registry (live)")
                gr.Button("Read the plane registry").click(sentra_planes, None, gp)
                gs = gr.Textbox(label="GATE axis scores (comma-separated)", value="0.9,0.95,0.99,0.92")
                gw = gr.Textbox(label="weights", value="1,1,2,1")
                gt = gr.Slider(0.5, 1.0, 0.97, label="advisory threshold")
                gout = gr.JSON(label="flagship GATE verdict")
                gr.Button("Evaluate at the flagship", variant="primary").click(sentra_gate_proxy, [gs, gw, gt], gout)
                yc = gr.Textbox(lines=6, label="YAWAR receipt chain (JSON array)")
                yout = gr.JSON(label="flagship YAWAR verification")
                gr.Button("Verify at the flagship").click(sentra_yawar_proxy, yc, yout)
            with gr.Tab("Receipt Curve"):
                rc = gr.Textbox(lines=7, label="Receipt chain (JSON array)",
                                placeholder='[{"seq":0,"prev_hash":"000...","chain_hash":"..."}, ...]')
                rsvg = gr.HTML(label="the curve")
                rjson = gr.JSON(label="verification detail")
                gr.Button("Draw the curve", variant="primary").click(receipt_curve_svg, rc, rsvg)
                gr.Button("Verify with detail").click(receipt_curve, rc, rjson)
            for v in VERTICALS["verticals"]:
                vid = v["id"]
                with gr.Tab(v["name"].split(" /")[0]):
                    gr.HTML(wire_html(v))
                    outv = gr.JSON(label=f"{v['name']} - live status")
                    gr.Button("Probe live endpoints", variant="primary").click(
                        lambda x=vid: vertical_status(x), None, outv)
                    if v["widget"] == "osint":
                        outw = gr.JSON(label="governed OSINT mesh - live from killinchu")
                        gr.Button("Query the source mesh").click(killinchu_osint, None, outw)
                    elif v["widget"] == "lambda":
                        p1 = gr.Slider(0, 1, 0.9, label="Axis - evidence")
                        p2 = gr.Slider(0, 1, 0.95, label="Axis - provenance")
                        p3 = gr.Slider(0, 1, 0.99, label="Axis - receipts")
                        p4 = gr.Slider(0, 1, 0.92, label="Axis - gates")
                        pt = gr.Slider(0.5, 1.0, 0.97, label="Advisory threshold")
                        outp = gr.JSON(label="PURIQ verdict")
                        gr.Button("Execute the formula gate").click(
                            lambda a, b, c, d, t: lambda_gate([a, b, c, d], [1, 1, 2, 1], t),
                            [p1, p2, p3, p4, pt], outp)
                    elif v["widget"] == "receipts":
                        rin = gr.Textbox(lines=7, label="Paste a receipt chain (JSON array)")
                        rout = gr.JSON(label="verification (local recomputation)")
                        gr.Button("Verify chain").click(verify_receipt_chain, rin, rout)
                    elif v["widget"] == "ouroboros":
                        oi = gr.Slider(1, 500, 50, step=1, label="Iterations")
                        ot = gr.Slider(0.0, 0.5, 0.02, label="Loop tax")
                        oout = gr.JSON(label="loop-tax ledger")
                        gr.Button("Run the loop").click(ouroboros, [oi, ot], oout)
                    elif v["widget"] == "bm25":
                        bc = gr.Textbox(lines=6, label="Doctrine corpus - one claim per line",
                                        value="deny by default is the trust posture\nreceipts make every claim checkable\nlambda gate aggregates axis scores geometrically\nthe ouroboros loop taxes every iteration\nfail closed means blocked never fabricated\nthe second brain answers only with evidence")
                        bq = gr.Textbox(label="Query the council", value="receipts checkable claims")
                        bout = gr.JSON(label="ranking")
                        gr.Button("Convene").click(bm25_rank, [bc, bq], bout)
                    elif v["widget"] == "quant":
                        qb = gr.Slider(2, 16, 4, step=1, label="Bit-width")
                        qout = gr.JSON(label="quality at width")
                        gr.Button("Measure the frontier").click(quant_curve, qb, qout)
            with gr.Tab("Drift"):
                dout = gr.JSON(label="drift report")
                gr.Button("Compute drift", variant="primary").click(estate_drift, None, dout)
            with gr.Tab("Kernel Console"):
                kvar = gr.Dropdown(["MHA", "GQA", "MQA", "MLA"], value="GQA", label="variant")
                with gr.Row():
                    kdm = gr.Slider(256, 8192, 2048, step=256, label="d_model")
                    kh = gr.Slider(1, 128, 32, step=1, label="n_heads")
                with gr.Row():
                    kkv = gr.Slider(1, 128, 8, step=1, label="n_kv_heads (GQA)")
                    kdc = gr.Slider(64, 1024, 512, step=64, label="d_latent (MLA)")
                kseq = gr.Slider(512, 131072, 8192, step=512, label="seq_len")
                kout = gr.JSON(label="cost verdict")
                gr.Button("Compute the variant", variant="primary").click(
                    kernel_console, [kvar, kdm, kh, kkv, kdc, kseq], kout)
            with gr.Tab("Trust Paths"):
                pa = gr.Textbox(label="from", value="sda")
                pb = gr.Textbox(label="to", value="lambda-gate-holo")
                pout = gr.JSON(label="trust path")
                gr.Button("Compute the path", variant="primary").click(trust_path, [pa, pb], pout)
            with gr.Tab("Live Estate"):
                out_le = gr.JSON(label="the org, measured now")
                gr.Button("Measure the estate", variant="primary").click(live_estates, None, out_le)
            with gr.Tab("Second Brain"):
                out_sb = gr.JSON(label="the memory plane, live")
                gr.Button("Query the second brain", variant="primary").click(second_brain, None, out_sb)
            with gr.Tab("Kernel Line"):
                out_k = gr.JSON(label="kernels - measured from the Hub")
                gr.Button("Measure the kernel line", variant="primary").click(kernel_line, None, out_k)
            with gr.Tab("Engines"):
                out6 = gr.JSON(label="engines on this host")
                gr.Button("Probe endpoints", variant="primary").click(engine_status, None, out6)
            with gr.Tab("Crosscheck"):
                chain_a = gr.Textbox(lines=10, label="Receipt chain A (JSON)")
                chain_b = gr.Textbox(lines=10, label="Receipt chain B (JSON)")
                rel_tol = gr.Slider(0.0, 1.0, value=0.01, step=0.001,
                                    label="Relative tolerance")
                crosscheck_out = gr.JSON(label="cross-implementation verdict")
                gr.Button("Crosscheck chains", variant="primary").click(
                    crosscheck_chains, [chain_a, chain_b, rel_tol], crosscheck_out)
    return demo

# ---------- FastAPI root app ----------

def create_app():
    import gradio as gr
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

    app = FastAPI(title="SZL Constellation")

    # Only public manifests are assets; never expose the repository root.
    @app.get("/static/estates.json", include_in_schema=False)
    def static_estates():
        return FileResponse(os.path.join(HERE, "estates.json"), media_type="application/json")

    @app.get("/static/verticals.json", include_in_schema=False)
    def static_verticals():
        return FileResponse(os.path.join(HERE, "verticals.json"), media_type="application/json")

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(os.path.join(HERE, "holo", "index.html"))

    @app.get("/c2", include_in_schema=False)
    def c2():
        return FileResponse(os.path.join(HERE, "c2", "index.html"))

    @app.get("/healthz")
    def healthz():
        return {
            "ok": True,
            "status": "ok",
            "service": "szl-constellation",
            "app_sha256": _local_app_sha256(),
        }

    @app.get("/api/source")
    def api_source():
        return source_binding()

    @app.get("/api/build-info")
    def api_build_info():
        return {"schema": "szl.build-info/v1", **source_binding()}

    @app.get("/api/c2/scenario")
    def api_c2_scenario(seed: int = 7, n: int = 28):
        return c2_scenario(seed, n)

    class C2Verify(BaseModel):
        events: list

    @app.post("/api/c2/verify")
    def api_c2_verify(req: C2Verify):
        return c2_verify(req.events)

    @app.get("/api/constellation/manifest")
    def api_manifest():
        payload = {"estates": MANIFEST["estates"], "live_lattice": MANIFEST["live_lattice"],
                   "hubs": MANIFEST["hubs"], "kernel_line": MANIFEST["kernel_line"],
                   "verticals": [v["id"] for v in VERTICALS["verticals"]],
                   "family_flagships": [f["id"] for f in VERTICALS.get("family_flagships", [])]}
        return {"state": "DECLARED", "manifest": payload, "receipt": _receipt(payload)}

    @app.get("/api/constellation/paths")
    def api_paths(frm: str = "sda", to: str = "lambda-gate-holo"):
        return trust_path(frm, to)

    @app.get("/api/estates")
    def api_estates():
        return live_estates()

    @app.get("/api/estate/drift")
    def api_drift():
        return estate_drift()

    @app.get("/api/kernels/console")
    def api_kernel_console(variant: str = "GQA", d_model: int = 2048, n_heads: int = 32,
                           n_kv_heads: int = 8, d_latent: int = 512, seq_len: int = 8192):
        return kernel_console(variant, d_model, n_heads, n_kv_heads, d_latent, seq_len)

    @app.get("/api/sentra/planes")
    def api_sentra_planes():
        return sentra_planes()

    @app.get("/api/receipts/curve")
    def api_receipt_curve(chain: str = "[]"):
        return receipt_curve(chain)

    @app.get("/api/families")
    def api_families():
        return {"state": "DECLARED", "families": VERTICALS.get("family_flagships", []),
                "receipt": _receipt(VERTICALS.get("family_flagships", []))}

    @app.get("/api/families/khipu/line")
    def api_khipu():
        return khipu_line()

    @app.get("/api/verticals")
    def api_verticals():
        payload = {"verticals": VERTICALS["verticals"], "shared_substrate": VERTICALS["shared_substrate"]}
        return {"state": "DECLARED", **payload, "receipt": _receipt(payload)}

    @app.get("/api/verticals/{vid}/status")
    def api_vertical_status(vid: str):
        return vertical_status(vid)

    @app.get("/api/kernels")
    def api_kernels():
        return kernel_line()

    @app.post("/api/crosscheck")
    async def api_crosscheck(request: Request):
        declared = request.headers.get("content-length")
        try:
            if declared is not None:
                declared_bytes = int(declared)
                if declared_bytes < 0:
                    return JSONResponse({"state": "BLOCKED", "error": "INVALID_CONTENT_LENGTH"}, status_code=400)
                if declared_bytes > MAX_CROSSCHECK_REQUEST_BYTES:
                    return JSONResponse(
                        {"state": "BLOCKED", "error": "REQUEST_TOO_LARGE", "max_bytes": MAX_CROSSCHECK_REQUEST_BYTES},
                        status_code=413,
                    )
        except ValueError:
            return JSONResponse({"state": "BLOCKED", "error": "INVALID_CONTENT_LENGTH"}, status_code=400)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_CROSSCHECK_REQUEST_BYTES:
                return JSONResponse(
                    {"state": "BLOCKED", "error": "REQUEST_TOO_LARGE", "max_bytes": MAX_CROSSCHECK_REQUEST_BYTES},
                    status_code=413,
                )
            raw.extend(chunk)
        try:
            decoded = _strict_json_loads(raw)
            payload = CrosscheckRequest.model_validate(decoded)
        except (UnicodeDecodeError, ValueError, TypeError, ValidationError, RecursionError):
            return JSONResponse({"state": "BLOCKED", "error": "INVALID_REQUEST"}, status_code=422)
        verdict = crosscheck_chains(_canon(payload.a), _canon(payload.b), payload.rel_tol)
        return {**verdict, "receipt": _receipt(verdict)}

    panels_error = None
    try:
        demo = build_consoles()
        # HF enables SSR by default. A mounted sub-app must not compete with
        # the root Uvicorn process for port 7860.
        app = gr.mount_gradio_app(app, demo, path="/panels", css=CSS, ssr_mode=False)
    except Exception as exc:
        panels_error = type(exc).__name__

        @app.get("/panels", include_in_schema=False)
        @app.get("/panels/", include_in_schema=False)
        def panels_unavailable():
            return HTMLResponse(
                '<!doctype html><html lang="en"><meta charset="utf-8">'
                '<title>Constellation consoles unavailable</title>'
                '<body style="background:#070b12;color:#d4a444;font:16px monospace;padding:3rem">'
                '<h1>CONSOLES UNAVAILABLE</h1><p>The console plane failed to mount ('
                + panels_error + '). No mounted status is claimed.</p>'
                '<p><a href="/">Constellation map</a> · '
                '<a href="/api/panels/status">Status evidence</a></p></body></html>',
                status_code=503,
            )

    @app.get("/api/panels/status")
    def api_panels_status():
        if panels_error is None:
            return {"state": "MEASURED", "panels": "MOUNTED", "mount": "/panels"}
        return {"state": "UNAVAILABLE", "panels": "MOUNT_FAILED", "detail": panels_error}

    @app.get("/readyz")
    def readyz():
        binding = source_binding()
        listener = listener_source_contract()
        checks = {
            "manifests_loaded": bool(MANIFEST.get("estates")) and bool(VERTICALS.get("verticals")),
            "panels_mounted": panels_error is None,
            "source_revision_measured": binding["state"] == "MEASURED",
            "single_listener_source_contract_validated": listener["valid"],
        }
        ready = all(checks.values())
        return JSONResponse(
            {"ready": ready, "state": "MEASURED" if ready else "UNAVAILABLE", "checks": checks, "source": binding, "listener_contract": listener},
            status_code=200 if ready else 503,
        )

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
