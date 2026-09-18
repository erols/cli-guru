import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli_guru import context


class TestRedaction(unittest.TestCase):
    SECRETS = ["abc123", "sup3rs3cret", "eyJhbGc123", "hunter2", "xyz789"]

    def test_secrets_never_survive(self):
        cases = [
            "export API_KEY=abc123",
            "mysql -u root -psup3rs3cret",
            'curl -H "Authorization: Bearer eyJhbGc123" http://x',
            "DB_PASSWORD: hunter2",
            "aws --token=xyz789 s3 ls",
            "docker run -e MYSQL_ROOT_PASSWORD=hunter2 img",
        ]
        for line in cases:
            with self.subTest(line=line):
                out = context.redact(line)
                for secret in self.SECRETS:
                    self.assertNotIn(secret, out)

    def test_aws_key_id_removed_entirely(self):
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", context.redact("AKIAIOSFODNN7EXAMPLE"))

    def test_benign_commands_untouched(self):
        for line in ["ls -la", 'git commit -m "fix"', "psql -p 5432 localhost", "rsync -avz a/ b/"]:
            with self.subTest(line=line):
                self.assertEqual(context.redact(line), line)


class TestHistory(unittest.TestCase):
    def test_reads_env_and_limits(self):
        with mock.patch.dict(os.environ, {"CLIAI_HISTORY": "a\nb\nc\nd"}):
            self.assertEqual(context.history(2), "c\nd")

    def test_absent_env_is_empty(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(context.history(5), "")

    def test_history_is_redacted(self):
        with mock.patch.dict(os.environ, {"CLIAI_HISTORY": "export TOKEN=s3cret999"}):
            self.assertNotIn("s3cret999", context.history(5))


class TestListing(unittest.TestCase):
    def test_marks_dirs_and_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "adir").mkdir()
            for i in range(5):
                (root / f"f{i}.txt").touch()
            out = context.listing(root, max_files=3)
            self.assertIn("adir/", out)
            self.assertIn("more", out)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(context.listing(Path(tmp), 50), "(empty)")


class TestFileTypes(unittest.TestCase):
    def test_counts_extensions_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "a.py").touch()
            (root / "sub" / "b.py").touch()
            (root / "sub" / "c.md").touch()
            out = context.file_types(root)
            self.assertIn(".py", out)
            self.assertIn("2 .py", out)

    def test_skips_noise_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "junk.js").touch()
            (root / "real.py").touch()
            self.assertNotIn(".js", context.file_types(root))


class TestRender(unittest.TestCase):
    def test_omits_empty_sections(self):
        ctx = {
            "os": "Linux", "kernel": "6.1", "userland": "GNU coreutils", "shell": "bash",
            "cwd_display": "~/x", "files": "a b", "file_types": "", "git": "", "tools": "",
            "history": "",
        }
        out = context.render(ctx)
        self.assertNotIn("git:", out)
        self.assertNotIn("Recent commands", out)
        self.assertIn("Working directory: ~/x", out)


if __name__ == "__main__":
    unittest.main()
