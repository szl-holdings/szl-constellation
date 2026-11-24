import unittest
from mapping_study import link_fields, repo_reference


class MappingStudyTest(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(repo_reference("szl-holdings/a.b-c_1"), "a.b-c_1")

    def test_https(self):
        self.assertEqual(repo_reference("https://github.com/szl-holdings/nexus/tree/main"), "nexus")

    def test_host_suffix(self):
        self.assertIsNone(repo_reference("https://github.com.evil.example/szl-holdings/nexus"))

    def test_userinfo(self):
        self.assertIsNone(repo_reference("https://github.com@evil.example/szl-holdings/nexus"))

    def test_unrelated_owner(self):
        self.assertIsNone(repo_reference("https://github.com/other/nexus"))

    def test_embedded_reference(self):
        self.assertIsNone(repo_reference("https://evil.example/?q=szl-holdings/nexus"))

    def test_invalid_slug(self):
        for value in ("szl-holdings/..", "prefix szl-holdings/nexus", "szl-holdings/nexus/other"):
            with self.subTest(value=value):
                self.assertIsNone(repo_reference(value))

    def test_nested_fields_and_no_false_edges(self):
        result = link_fields({"children": [{"repo": "szl-holdings/nexus"},
                                          {"repo": "https://github.com.evil.example/szl-holdings/no"}],
                              "other": "https://github.com/szl-holdings/anatomy"})
        self.assertEqual([item["repo"] for item in result], ["nexus", "anatomy"])


if __name__ == "__main__":
    unittest.main()
