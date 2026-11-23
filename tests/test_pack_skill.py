from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
import stat

ROOT = Path(__file__).resolve().parents[1]
PACKER = ROOT / "tools" / "pack_skill.py"


class SkillPackageTests(unittest.TestCase):
    def build(self, output: Path) -> None:
        subprocess.run(
            [sys.executable, str(PACKER), "--out", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_archive_contains_version_and_specialized_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "article-finder.skill"
            self.build(output)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
        self.assertIn("article-finder/VERSION", names)
        self.assertIn("article-finder/requirements.txt", names)
        self.assertIn("article-finder/SKILL.md", names)
        for required in (
            "article-finder/CHANGELOG.md",
            "article-finder/index.html",
            "article-finder/app.js",
            "article-finder/styles.css",
            "article-finder/.github/workflows/tests.yml",
            "article-finder/vercel.json",
            "article-finder/api/index.py",
        ):
            self.assertIn(required, names)
        expected = {
            "systematic-search", "openalex-retrieval", "source-verification",
            "prisma-screening", "literature-synthesis", "citation-verification",
            "scientific-writing", "security-review", "ci-cd-release",
        }
        packaged = {
            name.split("/")[2]
            for name in names
            if name.startswith("article-finder/skills/") and name.endswith("/SKILL.md")
        }
        self.assertTrue(expected.issubset(packaged))
        self.assertFalse(any(name.lower().endswith((".pdf", ".pyc", ".skill")) for name in names))
        self.assertFalse(any("__pycache__" in name or "/dist/" in name for name in names))
        self.assertNotIn("article-finder/tests/test_pack_skill.py", names)

    def test_archive_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.skill"
            second = Path(directory) / "second.skill"
            self.build(first)
            self.build(second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_archive_has_safe_unique_regular_entries_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "article-finder.skill"
            self.build(output)
            with zipfile.ZipFile(output) as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                self.assertEqual(len(names), len(set(names)))
                for item in infos:
                    self.assertTrue(item.filename.startswith("article-finder/"))
                    self.assertNotIn("..", Path(item.filename).parts)
                    self.assertFalse(item.filename.startswith("/"))
                    mode = item.external_attr >> 16
                    self.assertTrue(stat.S_ISREG(mode))
                    self.assertFalse(stat.S_ISLNK(mode))
                    self.assertIn(stat.S_IMODE(mode), (0o644, 0o755))


if __name__ == "__main__":
    unittest.main()
