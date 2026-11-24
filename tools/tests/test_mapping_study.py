# test_mapping_study.py - regression battery for mapping_study.py v2 (PR64 F04).
# Covers: nested structures, dict-shaped containers, exact-host URL matching,
# deceptive hosts, .git normalization, parse-before-truncation, multi-link values,
# missing args/inputs, malformed snapshots. Stdlib only.
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "mapping_study.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("mapping_study", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LinkFieldTests(unittest.TestCase):
    def setUp(self):
        self.m = load_tool()

    def test_nested_lists_and_dicts(self):
        obj = {"a": [{"b": {"c": "szl-holdings/estate-cards"}}]}
        links = self.m.link_fields(obj)
        self.assertEqual(len(links), 1)
        self.assertIn("estate-cards", links[0]["repo_mentions"])

    def test_github_url_exact_host(self):
        obj = {"u": "https://github.com/szl-holdings/szl-portal"}
        links = self.m.link_fields(obj)
        self.assertEqual(links[0]["github_repos"], ["szl-portal"])

    def test_case_insensitive_host_and_github_suffix(self):
        obj = {"u": "https://GitHub.COM/szl-holdings/szl-portal.git"}
        links = self.m.link_fields(obj)
        self.assertEqual(links[0]["github_repos"], ["szl-portal"])

    def test_deceptive_host_rejected(self):
        obj = {"u": "https://github.com.evil.io/szl-holdings/szl-portal"}
        links = self.m.link_fields(obj)
        self.assertEqual(links, [])

    def test_subpath_host_rejected(self):
        obj = {"u": "https://api.github.com/szl-holdings/szl-portal"}
        links = self.m.link_fields(obj)
        self.assertEqual(links, [])

    def test_dot_separated_deception_rejected(self):
        obj = {"u": "host szl-holdings.github.com.evil.io referenced"}
        links = self.m.link_fields(obj)
        self.assertEqual(links, [])

    def test_parse_before_truncation(self):
        obj = {"u": "x" * 130 + " szl-holdings/far-away-repo"}
        links = self.m.link_fields(obj)
        self.assertIn("far-away-repo", links[0]["repo_mentions"])

    def test_multiple_links_one_value(self):
        obj = {"u": "szl-holdings/a and szl-holdings/b plus https://github.com/szl-holdings/c"}
        links = self.m.link_fields(obj)
        self.assertIn("a", links[0]["repo_mentions"])
        self.assertIn("b", links[0]["repo_mentions"])
        self.assertIn("c", links[0]["github_repos"])

    def test_external_github_url_is_link_not_estate_repo(self):
        obj = {"u": "https://github.com/other-org/thing"}
        links = self.m.link_fields(obj)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["github_repos"], [])
        self.assertEqual(links[0]["external_github_paths"], ["/other-org/thing"])

    def test_non_string_leaf_ignored(self):
        obj = {"n": 42, "z": None, "b": True}
        self.assertEqual(self.m.link_fields(obj), [])


class CountTests(unittest.TestCase):
    def setUp(self):
        self.m = load_tool()

    def test_dict_shaped(self):
        self.assertEqual(self.m.count_entries({"estates": [1, 2, 3]}, "estates"), 3)

    def test_list_shaped(self):
        self.assertEqual(self.m.count_entries([1, 2], "estates"), 2)


class CliTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *map(str, args)],
                               capture_output=True, text=True, check=False)

    def test_missing_args_exit_2(self):
        r = self.invoke()
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", r.stderr)

    def test_missing_inputs_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.invoke(d)
            self.assertEqual(r.returncode, 2)
            self.assertIn("missing input", r.stderr)

    def test_valid_run_and_snapshot_passthrough(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "estates.json").write_text(json.dumps([{"src": "szl-holdings/x"}]), encoding="utf-8")
            Path(d, "verticals.json").write_text(json.dumps([]), encoding="utf-8")
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps(["x"]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(out["counts"]["distinct_repos_referenced"], 1)
            self.assertEqual(out["counts"]["repos_in_org_snapshot"], 1)
            self.assertEqual(out["counts"]["repos_referenced_not_in_org_snapshot"], [])
            self.assertEqual(out["generation"]["org_snapshot_file"], "snap.json")

    def test_dangling_repo_reported(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "estates.json").write_text(json.dumps([{"src": "szl-holdings/dangling"}]), encoding="utf-8")
            Path(d, "verticals.json").write_text(json.dumps([]), encoding="utf-8")
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps(["other"]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["counts"]["repos_referenced_not_in_org_snapshot"], ["dangling"])

    def test_malformed_snapshot_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "estates.json").write_text(json.dumps([]), encoding="utf-8")
            Path(d, "verticals.json").write_text(json.dumps([]), encoding="utf-8")
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps([{"bad": "shape"}]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 2)
            self.assertIn("invalid snapshot shape", r.stderr)

    def test_missing_snapshot_file_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "estates.json").write_text(json.dumps([]), encoding="utf-8")
            Path(d, "verticals.json").write_text(json.dumps([]), encoding="utf-8")
            r = self.invoke(d, Path(d, "nope.json"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("missing snapshot file", r.stderr)


if __name__ == "__main__":
    unittest.main()
