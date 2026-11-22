from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseVersionTests(unittest.TestCase):
    def test_canonical_version_is_one_one_zero(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "1.1.0")

    def test_specialized_skills_match_canonical_version(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        skill_files = sorted((ROOT / "skills").rglob("SKILL.md"))
        self.assertGreaterEqual(len(skill_files), 9)
        for path in skill_files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn(version, path.read_text(encoding="utf-8"))

    def test_runtime_and_user_facing_versions_match(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        paths = (
            "README.md",
            "SKILL.md",
            "index.html",
            "scripts/web_api.py",
            "scripts/serve.py",
            "tests/test_http_server.py",
            ".github/workflows/tests.yml",
            "CHANGELOG.md",
            "references/evidence-records.md",
        )
        for relative in paths:
            with self.subTest(path=relative):
                content = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(version, content)
                self.assertNotIn("1.3.0", content)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [1.1.0]", changelog)
        self.assertNotIn("## [1.2.0]", changelog)
        self.assertNotIn("## [1.3.0]", changelog)


if __name__ == "__main__":
    unittest.main()
