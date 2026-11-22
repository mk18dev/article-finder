from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class SkillPackageTests(unittest.TestCase):
    def test_archive_contains_version_and_specialized_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "article-finder.skill"
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "pack_skill.py"), "--out", str(output)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

        self.assertIn("article-finder/VERSION", names)
        self.assertIn("article-finder/SKILL.md", names)
        expected = {
            "systematic-search",
            "openalex-retrieval",
            "source-verification",
            "prisma-screening",
            "literature-synthesis",
            "citation-verification",
            "scientific-writing",
            "security-review",
            "ci-cd-release",
        }
        packaged = {
            name.split("/")[1]
            for name in names
            if name.startswith("article-finder/skills/") and name.endswith("/SKILL.md")
        }
        self.assertTrue(expected.issubset(packaged))
        self.assertFalse(any(name.lower().endswith(".pdf") for name in names))
        self.assertFalse(any("__pycache__" in name or name.startswith("article-finder/dist/") for name in names))


if __name__ == "__main__":
    unittest.main()
