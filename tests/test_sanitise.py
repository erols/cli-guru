"""Highest-value tests in the suite: this output goes into a live shell prompt."""

import unittest

from cliai import sanitise


class TestCommand(unittest.TestCase):
    def test_model_output_shapes(self):
        cases = [
            ("find . -name x", "find . -name x"),
            ("```bash\nfind . -name x\n```", "find . -name x"),
            ("```\nls -la\n```", "ls -la"),
            ("`ls -la`", "ls -la"),
            ("$ ls -la", "ls -la"),
            ("# ls -la", "ls -la"),
            ("user@host:~$ ls -la", "ls -la"),
            ("PS > Get-ChildItem", "Get-ChildItem"),
            ("Here's the command:\n```\nls -la\n```", "ls -la"),
            ("Sure!\n\nls -la", "ls -la"),
            ("ls -la\nThis lists all files.", "ls -la"),
            ("  \n\n  ls -la  \n", "ls -la"),
            ("This command will list files.\nls -la", "ls -la"),
            ("", ""),
            ("   ", ""),
        ]
        for raw, want in cases:
            with self.subTest(raw=raw):
                self.assertEqual(sanitise.command(raw), want)

    def test_rejects_degenerate_repetition(self):
        """Observed failure: the model looped `--quiet` until the token cap."""
        self.assertEqual(sanitise.command("git diff " + "--quiet " * 40), "")

    def test_rejects_absurdly_long_line(self):
        self.assertEqual(sanitise.command("x " * 400), "")

    def test_rejects_model_prose_and_refusals(self):
        """Without this, a refusal is pasted straight into a live shell prompt."""
        for raw in [
            "Sorry, I cannot help with that.",
            "I am unable to determine the command.",
            "This will list all files in the directory.",
            "As an AI, I do not have access to your filesystem.",
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(sanitise.command(raw), "")

    def test_keeps_commands_that_end_in_a_dot(self):
        """`cp x .` must survive the prose filter: the dot is its own token."""
        for cmd in ["cp file.txt .", "ls .", 'echo "done."', 'git commit -m "fix the bug."']:
            with self.subTest(cmd=cmd):
                self.assertEqual(sanitise.command(cmd), cmd)

    def test_keeps_legitimately_repetitive_command(self):
        cmd = "tar -czf a.tgz src tests docs"
        self.assertEqual(sanitise.command(cmd), cmd)

    def test_preserves_quotes_and_pipes(self):
        cmd = "find . -name '*.py' -exec wc -l {} + | awk '{s+=$1} END {print s}'"
        self.assertEqual(sanitise.command(cmd), cmd)


class TestProse(unittest.TestCase):
    def test_strips_fences_keeps_body(self):
        self.assertEqual(sanitise.prose("```\nline one\nline two\n```"), "line one\nline two")

    def test_strips_markdown_for_terminal_reading(self):
        raw = "- **--oneline**: shows `one line`.\n## Summary\nDone."
        out = sanitise.prose(raw)
        for noise in ("**", "`", "##"):
            self.assertNotIn(noise, out)
        self.assertIn("--oneline", out)
        self.assertIn("one line", out)

    def test_collapses_blank_runs(self):
        self.assertEqual(sanitise.prose("a\n\n\n\nb"), "a\n\nb")

    def test_empty(self):
        self.assertEqual(sanitise.prose(""), "")


if __name__ == "__main__":
    unittest.main()
