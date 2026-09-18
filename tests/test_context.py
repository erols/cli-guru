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
        with mock.patch.dict(os.environ, {"CLI_GURU_HISTORY": "a\nb\nc\nd"}):
            self.assertEqual(context.history(2), "c\nd")

    def test_absent_env_is_empty(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(context.history(5), "")

    def test_history_is_redacted(self):
        with mock.patch.dict(os.environ, {"CLI_GURU_HISTORY": "export TOKEN=s3cret999"}):
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


class TestRedactionGaps(unittest.TestCase):
    """Shapes that survived redaction until a pre-launch review found them.

    History goes into the prompt and the prompt crosses the network to whatever
    $OLLAMA_HOST names, over plain HTTP. These are credentials, so they must not.
    """

    LEAKS = [
        ('curl -H "Authorization: Basic dXNlcjpwYXNzd29yZA==" x', "dXNlcjpwYXNzd29yZA=="),
        ("curl -u admin:hunter2 https://x", "hunter2"),
        ("docker login -p hunter2secret registry.io", "hunter2secret"),
        ("openssl rsa -passin pass:hunter2 -in k.pem", "hunter2"),
        ("curl --user bob:s3cr3tpw https://x", "s3cr3tpw"),
    ]

    # Over-redaction is not free either: it costs the model context it uses.
    # These are ports, uids and prose, not secrets.
    KEEP = [
        "docker run -u 1000:1000 -p 8080:80 img",
        "docker run -p 127.0.0.1:8080:80 img",
        "docker run -p [::1]:8080:80 img",
        "psql -p 5432 -h localhost",
        "ssh -p 2222 host",
        'git commit -m "fix the -p flag"',
    ]

    def test_credentials_are_redacted(self):
        for line, secret in self.LEAKS:
            with self.subTest(line=line):
                self.assertNotIn(secret, context.redact(line))

    def test_ports_and_uids_survive(self):
        for line in self.KEEP:
            with self.subTest(line=line):
                self.assertEqual(context.redact(line), line)


class TestGitPrivacyAndSafety(unittest.TestCase):
    def test_git_commands_disable_fsmonitor(self):
        """A repo's own .git/config can name a command git will run. Context is
        assembled wherever the user stands, including an untrusted checkout."""
        self.assertEqual(context._GIT[:1], ["git"])
        self.assertIn("core.fsmonitor=", context._GIT)

    def test_identity_is_never_collected(self):
        """`git config user.name` is the user's real name and helps write no
        command. It used to be sent on every keypress."""
        calls = []

        def spy(cmd, timeout=2.0, cwd=None):
            calls.append(cmd)
            return "true" if "rev-parse" in cmd and "--is-inside-work-tree" in cmd else ""

        with mock.patch.object(context, "_run", spy):
            out = context.git_info(Path("."))
        for cmd in calls:
            self.assertNotIn("user.name", cmd, f"collected identity: {cmd}")
        self.assertNotIn("user", out)


if __name__ == "__main__":
    unittest.main()
