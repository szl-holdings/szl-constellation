"""No-network privacy, cardinality and evidence regression for public 3D atlas."""
from __future__ import annotations
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import atlas_public as atlas


STAMP = datetime(2026, 11, 17, 7, 15, tzinfo=timezone.utc)


def obj(name, *, private=False, **kwargs):
    return SimpleNamespace(id="SZLHOLDINGS/"+name, private=private,
                           sha="a"*40, last_modified=STAMP,
                           tags=["license:apache-2.0","public"], **kwargs)


class PublicAtlasTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/"verticals.json"
        self.path.write_text(json.dumps({
            "generated":"2026-09-04T00:00:00Z",
            "verticals":[{
                "id":"killinchu", "name":"Killinchu",
                "domain":"Maritime resilience",
                "spaces":["SZLHOLDINGS/killinchu","SZLHOLDINGS/PRIVATE-NOT-LISTED"],
                "models":["Khipu"], "datasets":["test-public"],
                "repos":["szl-holdings/private-sensitive-repo"],
            }]
        }),encoding="utf-8")
        self.rows={
            "space":[obj("killinchu",sdk="docker"),obj("SECRET-SPACE",private=True,sdk="docker")],
            "model":[obj("Khipu"),obj("SECRET-MODEL",private=True)],
            "dataset":[obj("test-public"),obj("SECRET-DATASET",private=True)],
        }

    def collect(self):
        return atlas.collect(lister=lambda kind,limit:self.rows[kind],
                             topology_path=self.path,now=STAMP)

    def test_public_only_counts_and_all_edges_explicit(self):
        result=self.collect()
        self.assertEqual(result["counts"],{"space":1,"model":1,"dataset":1})
        self.assertEqual(result["declared_verticals"],1)
        self.assertEqual(len(result["nodes"]),4)
        self.assertEqual(len(result["links"]),3)
        self.assertEqual(result["state"],"OBSERVED_PUBLIC_HUB_METADATA")
        self.assertEqual(result["scope"],"ANONYMOUS_PUBLIC_HUB_ONLY")
        self.assertTrue(result["private_assets_excluded"])
        text=json.dumps(result)
        for forbidden in ("SECRET-SPACE","SECRET-MODEL","SECRET-DATASET",
                          "PRIVATE-NOT-LISTED","private-sensitive-repo"):
            self.assertNotIn(forbidden,text)
        self.assertFalse(result["production_qualified"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["runtime_readiness"],"NOT_EVALUATED")
        for link in result["links"]:
            self.assertEqual(link["kind"],"DECLARED_MEMBERSHIP_MATCHED_TO_PUBLIC_HUB")

    def test_direct_ids_and_licenses_are_metadata_not_eval(self):
        result=self.collect()
        space=[n for n in result["nodes"] if n["kind"]=="space"][0]
        self.assertEqual(space["url"],"https://huggingface.co/spaces/SZLHOLDINGS/killinchu")
        self.assertEqual(space["source_revision"],"a"*40)
        self.assertIn("license:apache-2.0",space["tags"])
        self.assertEqual(space["operational_readiness"],"NOT_EVALUATED")
        self.assertEqual(space["verticals"],["killinchu"])

    def test_unassigned_public_resource_remains_visible_without_invented_edge(self):
        self.rows["space"].append(obj("novel",sdk="docker"))
        result=self.collect()
        node=next(n for n in result["nodes"] if n["id"]=="space:SZLHOLDINGS/novel")
        self.assertEqual(node["verticals"],[])
        self.assertFalse(any(l["target"]==node["id"] for l in result["links"]))

    def test_only_literal_false_is_public(self):
        self.rows["model"]=[obj("Khipu",private=None),obj("Khipu2",private="false")]
        result=self.collect()
        self.assertEqual(result["counts"]["model"],0)

    def test_other_organization_cannot_enter_atlas(self):
        self.rows["model"]=[SimpleNamespace(id="someoneelse/private",private=False)]
        self.assertEqual(self.collect()["counts"]["model"],0)

    def test_complete_census_required_and_duplicate_identifiers_rejected(self):
        self.rows["space"]=[obj("killinchu") for _ in range(atlas.MAX_SPACES)]
        with self.assertRaisesRegex(atlas.AtlasError,"INCOMPLETE_PUBLIC_LIST"):
            self.collect()
        self.rows["space"]=[obj("killinchu"),obj("killinchu")]
        with self.assertRaisesRegex(atlas.AtlasError,"DUPLICATE_PUBLIC_ID"):
            self.collect()

    def test_unavailable_provider_does_not_return_partial_graph(self):
        def fail(kind,limit):
            if kind=="dataset":raise TimeoutError("PRIVATE_UPSTREAM_DATA")
            return self.rows[kind]
        with self.assertRaises(TimeoutError):
            atlas.collect(lister=fail,topology_path=self.path,now=STAMP)

    def test_malformed_topology_rejected(self):
        self.path.write_text('{"verticals":[{"id":"../secret","name":"bad"}]}')
        with self.assertRaisesRegex(atlas.AtlasError,"VERTICAL_IDENTITY_INVALID"):
            self.collect()

    def test_duplicate_vertical_rejected(self):
        content=json.loads(self.path.read_text())
        content["verticals"].append(copy.deepcopy(content["verticals"][0]))
        self.path.write_text(json.dumps(content))
        with self.assertRaisesRegex(atlas.AtlasError,"VERTICAL_IDENTITY_INVALID"):
            self.collect()

    def test_checksum_stable_and_changes_on_public_input(self):
        first=self.collect()
        second=self.collect()
        self.assertEqual(first["observation_sha256"],second["observation_sha256"])
        self.rows["model"]=[obj("A-DIFFERENT-PUBLIC-MODEL")]
        third=self.collect()
        self.assertNotEqual(first["observation_sha256"],third["observation_sha256"])
        body={k:v for k,v in first.items() if k!="observation_sha256"}
        expected=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),
                      allow_nan=False,ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(first["observation_sha256"],expected)

    def test_backend_cache_does_not_use_expired_snapshot_after_failure(self):
        original=atlas._cache
        self.addCleanup(lambda:setattr(atlas,"_cache",original))
        atlas._cache=None
        count=[0]
        def collect():
            count[0]+=1
            if count[0]>1:raise RuntimeError("NO_FAKE_GREEN")
            return {"state":"OBSERVED_PUBLIC_HUB_METADATA"}
        with patch.object(atlas,"collect",side_effect=collect):
            with patch.object(atlas.time,"monotonic",side_effect=[100,100,401]):
                self.assertEqual(atlas.cached_public_atlas()["state"],"OBSERVED_PUBLIC_HUB_METADATA")
                with self.assertRaisesRegex(RuntimeError,"NO_FAKE_GREEN"):
                    atlas.cached_public_atlas()
        self.assertEqual(count[0],2)

    def test_static_vendor_and_graph_assets_present(self):
        root=Path(__file__).resolve().parents[1]
        for rel in ("atlas/index.html","atlas/atlas.js","atlas/atlas.css",
                    "atlas/vendor/three.module.js","atlas/vendor/three.core.js",
                    "atlas/vendor/OrbitControls.js","atlas/vendor/THREE-LICENSE.txt"):
            self.assertTrue((root/rel).is_file(),rel)
        html=(root/"atlas/index.html").read_text(encoding="utf-8")
        self.assertIn('src="/atlas/atlas.js"',html)
        self.assertIn('href="#directory"',html)
        js=(root/"atlas/atlas.js").read_text(encoding="utf-8")
        self.assertIn("THREE.InstancedMesh",js)
        self.assertIn("THREE.Raycaster",js)
        self.assertIn("private_assets_excluded !== true",js)
        self.assertNotIn(".innerHTML",js)
        pinned={
            "three.module.js":"104f56145899722094556490d787aae0617cc2fc3382f31df02d724ea1aee341",
            "three.core.js":"613e370f76638fdef83926642bf256dc9615684922de1ce1f63a8583e5d78578",
            "OrbitControls.js":"a747d56dd959510407777f1800792b2b52c0a435980fd6e40caf303d8a674b9e",
            "THREE-LICENSE.txt":"8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc",
        }
        for name,expected in pinned.items():
            with self.subTest(vendor=name):
                self.assertEqual(hashlib.sha256((root/"atlas/vendor"/name).read_bytes()).hexdigest(), expected)


if __name__=="__main__":
    unittest.main()
