"""Offline qualification regressions; no provider, signing, or runtime startup."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosscheck import GENESIS, canonical, crosscheck_chains

def context():
    return {"machine": {"identity": "fixture", "cpu": "fixture", "os": "fixture", "python": "fixture"},
            "dataset_revision": "fixture", "model_revision": "model-a",
            "parameters": {"fixture": True},
            "input_hashes": {"corpus": "a"*64, "queries": "b"*64, "qrels": "c"*64},
            "source": {"repository": "synthetic/harness-a", "commit": "d"*40}}

def chain(*, state="MEASURED", ctx=None, metrics=None, previous=GENESIS, lane="shared"):
    payload = {"context": context() if ctx is None else ctx,
               "results": [{"state": state, "engine": lane, "runs": 3,
                            "metrics": {"latency": 1.0} if metrics is None else metrics}]}
    return [{**payload, "prev_hash": previous,
             "chain_hash": hashlib.sha256((previous + canonical(payload)).encode()).hexdigest()}]

def compare(a, b):
    return crosscheck_chains(json.dumps(a), json.dumps(b))

class QualificationTests(unittest.TestCase):
    def test_valid_context_and_distinct_harness_sources_compare(self):
        ctx=context(); ctx["source"]={"repository":"synthetic/harness-b","commit":"e"*40}
        result=compare(chain(),chain(ctx=ctx))
        self.assertEqual(result["verdict"],"CONSISTENT")
        self.assertEqual(result["state"],"MEASURED")
        self.assertEqual(result["lanes"][0]["metrics_compared"],1)

    def test_non_measured_states_never_compare_even_with_runs(self):
        for state in ("BLOCKED","SAMPLE","UNAVAILABLE",None,"measured"):
            with self.subTest(state=state):
                result=compare(chain(state=state),chain(state=state))
                self.assertEqual(result["verdict"],"INCOMPARABLE")
                self.assertNotEqual(result["state"],"MEASURED")
                self.assertNotIn("dual_receipt",result)

    def test_one_non_measured_side_cannot_compare(self):
        self.assertEqual(compare(chain(),chain(state="BLOCKED"))["verdict"],"INCOMPARABLE")

    def test_context_mismatches_are_incomparable(self):
        for key in ("model_revision","dataset_revision","parameters","machine","input_hashes"):
            ctx=context()
            if key=="input_hashes":ctx[key]["queries"]="f"*64
            elif key=="machine":ctx[key]["identity"]="other"
            elif key=="parameters":ctx[key]={"fixture":False}
            else:ctx[key]="other"
            with self.subTest(key=key):
                result=compare(chain(),chain(ctx=ctx))
                self.assertEqual(result["verdict"],"INCOMPARABLE")
                self.assertNotEqual(result["state"],"MEASURED")

    def test_incomplete_context_is_invalid(self):
        for key in context():
            ctx=context();del ctx[key]
            with self.subTest(key=key):
                self.assertEqual(compare(chain(ctx=ctx),chain())["state"],"INVALID")

    def test_malformed_context_is_invalid(self):
        for ctx in ({}, {"model_revision":"x"}, "bad"):
            self.assertEqual(compare(chain(ctx=ctx),chain())["state"],"INVALID")

    def test_duplicate_lane_is_invalid(self):
        first=chain()
        second=chain(previous=first[-1]["chain_hash"])
        self.assertEqual(compare(first+second,chain())["state"],"INVALID")

    def test_mixed_context_within_chain_is_invalid(self):
        first=chain();ctx=context();ctx["model_revision"]="other"
        second=chain(ctx=ctx,previous=first[-1]["chain_hash"],lane="other")
        self.assertEqual(compare(first+second,chain())["state"],"INVALID")

    def test_malformed_measured_metrics_are_invalid(self):
        for metrics in ({}, {"x":True}, {"x":"1"}):
            self.assertEqual(compare(chain(metrics=metrics),chain())["state"],"INVALID")

    def test_metric_math_is_unchanged(self):
        result=compare(chain(metrics={"x":1e308}),chain(metrics={"x":-1e308}))
        self.assertEqual(result["verdict"],"DIVERGENT")
        self.assertEqual(result["lanes"][0]["max_rel_delta"],2.0)
        self.assertEqual(compare(chain(metrics={"a":1}),chain(metrics={"b":1}))["verdict"],"INCOMPARABLE")

    def test_tampering_still_invalid(self):
        a=chain();a[0]["context"]["model_revision"]="tampered"
        self.assertEqual(compare(a,chain())["state"],"INVALID")

class ActualApiCallerTests(unittest.TestCase):
    """Execute exact API handler/model/helpers, not app startup or provider code."""
    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        from pydantic import BaseModel, ConfigDict, Field, ValidationError
        source=Path(__file__).resolve().parents[1]/"app.py"
        tree=ast.parse(source.read_text())
        names={"CrosscheckRequest","_reject_non_finite_json","_strict_json_loads","_canon","_receipt"}
        nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
        api=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=="api_crosscheck")
        api.decorator_list=[]
        nodes.append(api)
        ns=dict(json=json,hashlib=hashlib,time=time,Any=Any,BaseModel=BaseModel,ConfigDict=ConfigDict,
                Field=Field,ValidationError=ValidationError,Request=Request,JSONResponse=JSONResponse,
                MAX_CROSSCHECK_REQUEST_BYTES=1_000_000,crosscheck_chains=crosscheck_chains)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(source),"exec"),ns)
        app=FastAPI();app.post("/api/crosscheck")(ns["api_crosscheck"])
        cls.client=TestClient(app)

    def test_exact_handler_valid_and_rejected_qualifications(self):
        for a,b,verdict in ((chain(),chain(),"CONSISTENT"),
                            (chain(state="BLOCKED"),chain(state="SAMPLE"),"INCOMPARABLE"),
                            (chain(),chain(ctx={**context(),"model_revision":"other"}),"INCOMPARABLE")):
            response=self.client.post("/api/crosscheck",json={"a":a,"b":b})
            self.assertEqual(response.status_code,200)
            body=response.json();receipt=body.pop("receipt")
            self.assertEqual(body["verdict"],verdict)
            self.assertEqual(receipt["sha256"],hashlib.sha256(canonical(body).encode()).hexdigest())
            self.assertTrue(receipt["signature"].startswith("UNSIGNED_HONEST"))

if __name__=="__main__":
    unittest.main()

