# test_mapping_study.py - regression battery for mapping_study.py v3 (PR64 R02).
# Covers: nested structures, dict-shaped containers, exact-host URL matching,
# deceptive hosts (URL-only end-to-end), bare host strings, userinfo/port/
# trailing-dot hosts, external-org URLs, prose substring mentions NOT counted,
# whole-string repo paths (incl. .git suffix), parse-before-truncation,
# multi-link values, edge record semantics (R04), CLI fail-closed classes
# (R05: usage/missing-input/invalid-JSON/wrong-shape/malformed snapshot),
# end-to-end CLI aggregates (distinct repos, edges, dangling, deceptive
# absent from stdout). Stdlib only.
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

    def one(self, value):
        return self.m.link_fields({"u": value})

    def test_nested_lists_and_dicts(self):
        obj = {"a": [{"b": {"c": "szl-holdings/estate-cards"}}]}
        links = self.m.link_fields(obj)
        self.assertEqual(len(links), 1)
        self.assertIn("estate-cards", links[0]["repo_mentions"])

    def test_github_url_exact_host(self):
        links = self.one("https://github.com/szl-holdings/szl-portal")
        self.assertEqual(links[0]["github_repos"], ["szl-portal"])
        self.assertEqual(links[0]["repo_mentions"], [])

    def test_case_insensitive_host_and_github_suffix(self):
        links = self.one("https://GitHub.COM/szl-holdings/szl-portal.git")
        self.assertEqual(links[0]["github_repos"], ["szl-portal"])

    def test_deceptive_host_rejected(self):
        links = self.one("https://github.com.evil.io/szl-holdings/szl-portal")
        self.assertEqual(links, [])
        self.assertEqual(self.m.link_fields({"u": "https://github.com.evil.io/szl-holdings/szl-portal"}), [])

    def test_subpath_host_rejected(self):
        links = self.one("https://api.github.com/szl-holdings/szl-portal")
        self.assertEqual(links, [])

    def test_bare_szl_holdings_github_host_string(self):
        links = self.one("szl-holdings.github.com")
        self.assertEqual(links, [])

    def test_dot_separated_deception_in_prose_rejected(self):
        links = self.one("host szl-holdings.github.com.evil.io referenced")
        self.assertEqual(links, [])

    def test_prose_substring_mentions_not_counted(self):
        links = self.one("see szl-holdings/foo and szl-holdings/bar in prose text")
        self.assertEqual(links, [])
        self.assertEqual(self.m.link_fields({"u": "szl-holdings/baz mentioned"}), [])

    def test_userinfo_host_url_accepted(self):
        links = self.one("https://user:pass@github.com/szl-holdings/p2")
        self.assertEqual(links[0]["github_repos"], ["p2"])

    def test_port_host_url_accepted(self):
        links = self.one("https://github.com:443/szl-holdings/p1")
        self.assertEqual(links[0]["github_repos"], ["p1"])

    def test_trailing_dot_host_accepted(self):
        links = self.one("https://github.com./szl-holdings/p3")
        self.assertEqual(links[0]["github_repos"], ["p3"])

    def test_external_github_url_is_link_not_estate_repo(self):
        links = self.one("https://github.com/other-org/thing")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["github_repos"], [])
        self.assertEqual(links[0]["repo_mentions"], [])
        self.assertEqual(links[0]["external_github_paths"], ["/other-org/thing"])

    def test_full_repo_path_value_with_git_suffix_and_slash(self):
        links = self.one("szl-holdings/plain-repo.git/")
        self.assertEqual(links[0]["repo_mentions"], ["plain-repo"])
        self.assertEqual(links[0]["github_repos"], [])

    def test_parse_before_truncation_whole_string(self):
        name = "r" * 130
        links = self.one("szl-holdings/" + name)
        self.assertIn(name, links[0]["repo_mentions"])
        self.assertEqual(len(links[0]["value_head"]), 60)

    def test_multiple_github_urls_one_value(self):
        links = self.one("https://github.com/szl-holdings/a and https://github.com/szl-holdings/b")
        self.assertEqual(sorted(links[0]["github_repos"]), ["a", "b"])
        self.assertEqual(links[0]["repo_mentions"], [])

    def test_non_string_leaf_ignored(self):
        obj = {"n": 42, "z": None, "b": True}
        self.assertEqual(self.m.link_fields(obj), [])


class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.m = load_tool()

    def test_edges_one_per_repo_not_per_field(self):
        obj = {"u": "https://github.com/szl-holdings/a and https://github.com/szl-holdings/b"}
        links = self.m.link_fields(obj)
        edges = self.m.edge_records("estates", links)
        self.assertEqual(len(edges), 2)
        self.assertEqual(sorted(e["repo"] for e in edges), ["a", "b"])

    def test_edge_dedupe_same_field_same_repo(self):
        obj = {"u": "https://github.com/szl-holdings/a and https://github.com/szl-holdings/a"}
        links = self.m.link_fields(obj)
        edges = self.m.edge_records("estates", links)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["kind"], "github_url")

    def test_edge_kinds_and_sources(self):
        obj = {"a": "szl-holdings/x", "b": "https://github.com/szl-holdings/y"}
        links = self.m.link_fields(obj)
        edges = self.m.edge_records("verticals", links)
        kinds = {(e["repo"], e["kind"]) for e in edges}
        self.assertEqual(kinds, {("x", "repo_path"), ("y", "github_url")})
        self.assertTrue(all(e["source"] == "verticals" for e in edges))


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

    def write_inputs(self, d, estates, verticals):
        Path(d, "estates.json").write_text(json.dumps(estates), encoding="utf-8")
        Path(d, "verticals.json").write_text(json.dumps(verticals), encoding="utf-8")

    def test_missing_args_exit_2(self):
        r = self.invoke()
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", r.stderr)

    def test_missing_inputs_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.invoke(d)
            self.assertEqual(r.returncode, 2)
            self.assertIn("missing input", r.stderr)

    def test_invalid_json_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "estates.json").write_text("{not json", encoding="utf-8")
            Path(d, "verticals.json").write_text("[]", encoding="utf-8")
            r = self.invoke(d)
            self.assertEqual(r.returncode, 2)
            self.assertIn("invalid JSON", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_wrong_top_level_type_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "estates.json").write_text("42", encoding="utf-8")
            Path(d, "verticals.json").write_text("[]", encoding="utf-8")
            r = self.invoke(d)
            self.assertEqual(r.returncode, 2)
            self.assertIn("top-level JSON must be an array or object", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_malformed_snapshot_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [], [])
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps([{"bad": "shape"}]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 2)
            self.assertIn("invalid snapshot shape", r.stderr)

    def test_missing_snapshot_file_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [], [])
            r = self.invoke(d, Path(d, "nope.json"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("missing snapshot file", r.stderr)

    def test_valid_run_and_snapshot_passthrough(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [{"src": "szl-holdings/x"}], [])
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps(["x"]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(out["generation"]["command"],
                             "python " + " ".join([str(TOOL), str(d), str(snap)]))
            self.assertEqual(out["generation"]["org_snapshot_file"], "snap.json")
            self.assertEqual(out["counts"]["distinct_repos_referenced"], 1)
            self.assertEqual(out["counts"]["repos_in_org_snapshot"], 1)
            self.assertEqual(out["counts"]["repos_referenced_not_in_org_snapshot"], [])
            self.assertEqual(out["counts"]["estate_to_repo_edges"], 1)
            self.assertEqual(out["edge_records"][0]["repo"], "x")

    def test_dangling_repo_reported(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [{"src": "szl-holdings/dangling"}], [])
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps(["other"]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 0)
            out = json.loads(r.stdout)
            self.assertEqual(out["counts"]["repos_referenced_not_in_org_snapshot"], ["dangling"])

    def test_deceptive_url_only_value_cli(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [{"src": "https://github.com.evil.io/szl-holdings/szl-portal"}], [])
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps(["szl-portal"]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 0)
            out = json.loads(r.stdout)
            self.assertEqual(out["counts"]["distinct_repos_referenced"], 0)
            self.assertEqual(out["counts"]["estate_to_repo_edges"], 0)
            self.assertEqual(out["counts"]["estate_link_fields"], 0)
            self.assertEqual(out["counts"]["repos_referenced_not_in_org_snapshot"], [])
            self.assertNotIn("github.com.evil.io", json.dumps(out["edge_records"]))

    def test_prose_only_value_cli(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [{"note": "we like szl-holdings/some-repo here"}], [])
            r = self.invoke(d)
            self.assertEqual(r.returncode, 0)
            out = json.loads(r.stdout)
            self.assertEqual(out["counts"]["distinct_repos_referenced"], 0)
            self.assertEqual(out["counts"]["estate_link_fields"], 0)
            self.assertEqual(out["counts"]["estate_to_repo_edges"], 0)

    def test_external_org_url_cli(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_inputs(d, [{"ref": "https://github.com/other-org/thing"}], [])
            snap = Path(d, "snap.json")
            snap.write_text(json.dumps(["thing"]), encoding="utf-8")
            r = self.invoke(d, snap)
            self.assertEqual(r.returncode, 0)
            out = json.loads(r.stdout)
            self.assertEqual(out["counts"]["distinct_repos_referenced"], 0)
            self.assertEqual(out["counts"]["repos_referenced_not_in_org_snapshot"], [])
            self.assertEqual(out["counts"]["external_github_paths"], ["/other-org/thing"])


if __name__ == "__main__":
    unittest.main()
