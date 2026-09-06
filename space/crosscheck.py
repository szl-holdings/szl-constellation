"""crosscheck - cross-implementation receipt verification for the constellation.

Two independent harnesses' receipt chains in; one verdict out:
CONSISTENT / DIVERGENT (metric + max relative delta named) / INCOMPARABLE
(no shared MEASURED lanes) / INVALID (a chain failed verification - fail closed).

Canonical home with tests and CI: github.com/szl-holdings/szl-crosscheck
(v0.1.0, 6/6 green pre-push). This module is byte-identical logic, placed here
for the constellation to import. UI wiring into /panels is intentionally NOT
done by overwrite - v4.2's app.py is owned by the parallel pipeline; mount
one tab calling crosscheck_chains() when convenient.
"""
from __future__ import annotations
import hashlib, json, math
from typing import Any, Dict, List, Tuple

GENESIS = "0" * 64


def _reject_non_finite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def canonical(o: Any) -> str:
    return json.dumps(
        o,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )


def _contains_non_finite(value: Any) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            try:
                if not math.isfinite(item):
                    return True
            except (OverflowError, TypeError, ValueError):
                return True
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)
    return False

def verify_chain(receipts: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if not receipts:
        return False, "empty chain"
    prev = GENESIS
    for i, r in enumerate(receipts):
        if not isinstance(r, dict):
            return False, f"receipt {i} is not an object"
        if r.get("prev_hash") != prev:
            return False, f"link broken at receipt {i}"
        payload = {k: v for k, v in r.items() if k not in ("prev_hash", "chain_hash")}
        if _contains_non_finite(payload):
            return False, f"non-finite numeric value at receipt {i}"
        try:
            expected = hashlib.sha256((prev + canonical(payload)).encode()).hexdigest()
        except (TypeError, ValueError, OverflowError, RecursionError):
            return False, f"non-canonical payload at receipt {i}"
        if r.get("chain_hash") != expected:
            return False, f"payload tampered at receipt {i}"
        results = r.get("results")
        if results is not None and (
            not isinstance(results, list)
            or any(not isinstance(result, dict) for result in results)
        ):
            return False, f"invalid results collection at receipt {i}"
        prev = r["chain_hash"]
    return True, f"chain valid ({len(receipts)} receipts)"

def _measured_lanes(chain: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    lanes: Dict[str, Dict[str, float]] = {}
    for r in chain:
        for res in (r.get("results") or []):
            if isinstance(res, dict) and res.get("runs") and isinstance(res.get("metrics"), dict):
                lane = str(res.get("engine") or res.get("lane") or res.get("name") or "run")
                lanes[lane] = {
                    k: float(v)
                    for k, v in res["metrics"].items()
                    if isinstance(v, (int, float))
                    and not isinstance(v, bool)
                    and math.isfinite(v)
                }
    return lanes

def crosscheck_chains(text_a: str, text_b: str, rel_tol: float = 0.01) -> Dict[str, Any]:
    """JSON strings in (paste-friendly), verdict dict out."""
    if not isinstance(rel_tol, (int, float)) or not math.isfinite(rel_tol) or not 0.0 <= rel_tol <= 1.0:
        return {"state": "INVALID", "detail": "relative tolerance must be finite and in [0,1]"}

    def parse(t):
        try:
            r = json.loads(t, parse_constant=_reject_non_finite_json)
            if isinstance(r, dict):
                r = [r]
            if not isinstance(r, list):
                raise ValueError("expected a JSON array of receipts")
            return r, None
        except Exception as e:
            return None, str(e)
    a, ea = parse(text_a)
    b, eb = parse(text_b)
    if ea:
        return {"state": "INVALID", "detail": f"chain A parse: {ea}"}
    if eb:
        return {"state": "INVALID", "detail": f"chain B parse: {eb}"}
    ok_a, det_a = verify_chain(a)
    ok_b, det_b = verify_chain(b)
    if not ok_a:
        return {"state": "INVALID", "detail": f"chain A: {det_a}"}
    if not ok_b:
        return {"state": "INVALID", "detail": f"chain B: {det_b}"}
    la, lb = _measured_lanes(a), _measured_lanes(b)
    shared = sorted(set(la) & set(lb))
    if not shared:
        return {"state": "MEASURED", "verdict": "INCOMPARABLE",
                "detail": "no shared MEASURED lanes", "a_lanes": sorted(la), "b_lanes": sorted(lb)}
    verdicts, overall = [], "CONSISTENT"
    metrics_compared = 0
    for lane in shared:
        common = sorted(set(la[lane]) & set(lb[lane]))
        if not common:
            verdicts.append({"lane": lane, "verdict": "INCOMPARABLE", "reason": "no shared metric keys"})
            continue
        worst, worst_k = 0.0, None
        metrics_compared += len(common)
        for k in common:
            va, vb = la[lane][k], lb[lane][k]
            scale = max(abs(va), abs(vb), 1e-12)
            # Scale first so finite opposite-sign extremes do not overflow.
            delta = abs(va / scale - vb / scale)
            if delta > worst:
                worst, worst_k = delta, k
        v = "CONSISTENT" if worst <= rel_tol else "DIVERGENT"
        if v == "DIVERGENT":
            overall = "DIVERGENT"
        verdicts.append({"lane": lane, "verdict": v, "max_rel_delta": round(worst, 6),
                         "worst_metric": worst_k, "metrics_compared": len(common)})
    if metrics_compared == 0:
        overall = "INCOMPARABLE"
    dual = hashlib.sha256(canonical({"a": a[-1]["chain_hash"], "b": b[-1]["chain_hash"],
                                     "verdicts": verdicts, "tol": rel_tol}).encode()).hexdigest()
    return {"state": "MEASURED", "verdict": overall, "lanes": verdicts, "tolerance": rel_tol,
            "dual_receipt": dual,
            "label": "cross-implementation verification - two chains, one truth test"}
