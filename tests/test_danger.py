"""Safety tests. This logic exists because models are unreliable at it:
qwen2.5-coder:3b missed 12/15 destructive commands when asked to spot them in
the prompt; nemotron-3-nano:4b caught all 15 but raised 9 false alarms on
read-only commands. Neither is acceptable, so cliai decides deterministically.
"""

import unittest

from cli_guru import danger

DESTRUCTIVE = [
    "rm -rf /var/log/*",
    "rm file.txt",
    "sudo rm -fr /opt/old",
    "dd if=/dev/zero of=/dev/sda",
    "mkfs.ext4 /dev/sdb1",
    "shred -u secret.txt",
    "git reset --hard origin/main",
    "git clean -fd",
    "git push --force origin main",
    "truncate -s 0 app.log",
    "find . -name '*.log' -delete",
    'find ./ -name "*.pyc" -exec rm {} +',
    "find . -name x | xargs rm",
    "echo x > important.conf",
    "docker system prune",
    "psql -c 'DROP TABLE users'",
]

SAFE = [
    "ls -la",
    "git log --oneline -n 5",
    "git status",
    "git push --force-with-lease origin main",
    "tar -tzvf archive.tar.gz",
    "df -h",
    "du -sh .",
    "grep -r TODO src/",
    "find . -name '*.py'",
    "find . -type f -exec grep TODO {} +",
    "echo hi > /dev/null",
    "rm -i old.txt",
    "cat notes.md",
    "ps aux",
]


class TestDetection(unittest.TestCase):
    def test_all_destructive_are_flagged(self):
        for cmd in DESTRUCTIVE:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(danger.check(cmd), f"missed: {cmd}")

    def test_no_false_alarms_on_read_only(self):
        """A false alarm is not harmless: warning fatigue makes real ones invisible."""
        for cmd in SAFE:
            with self.subTest(cmd=cmd):
                self.assertIsNone(danger.check(cmd), f"false alarm: {cmd}")

    def test_force_with_lease_is_not_force(self):
        self.assertIsNone(danger.check("git push --force-with-lease"))
        self.assertIsNotNone(danger.check("git push --force"))

    def test_redirect_to_devnull_is_safe(self):
        self.assertIsNone(danger.check("echo hi > /dev/null"))
        self.assertIsNotNone(danger.check("echo hi > file.txt"))

    def test_append_is_not_truncation(self):
        self.assertIsNone(danger.check("echo hi >> log.txt"))

    def test_interactive_rm_is_not_flagged(self):
        self.assertIsNone(danger.check("rm -i old.txt"))

    def test_read_only_wrapper_does_not_excuse_a_delete(self):
        """`find ... -exec rm` is a delete wearing a read-only command's name."""
        self.assertIsNotNone(danger.check('find . -name "*.pyc" -exec rm {} +'))

    def test_banner_format(self):
        self.assertTrue(danger.banner("rm -rf /").startswith("WARNING: "))
        self.assertIsNone(danger.banner("ls"))

    def test_empty_input(self):
        self.assertIsNone(danger.check(""))
        self.assertIsNone(danger.check("   "))


# Every one of these was silently cleared before `check` judged each segment
# separately: the line STARTS with a read-only command, and the _SAFE allowlist
# then excused everything after the separator too. `sudo ls; rm -rf /` is the
# one that shows why this mattered.
CHAINED_DESTRUCTIVE = [
    "echo hi; rm -rf /tmp/x",
    "ls; rm -rf ~/Documents",
    "cat /etc/hosts && rm -rf ~/Documents",
    "grep -r foo . ; mkfs.ext4 /dev/sda",
    "find . -name '*.log' -newer x; dd if=/dev/zero of=/dev/sda",
    "df -h; git reset --hard",
    "man ls; shred ~/.ssh/id_rsa",
    "sudo ls; rm -rf /",
    "ls || rm -rf ~/Documents",
    "ls & rm -rf /tmp/x",
    "ls; echo still safe; rm -rf /tmp/x",
    "echo one\nrm -rf /tmp/x",
    # Substitutions run too, including inside double quotes.
    "ls $(rm -rf ~/Documents)",
    "ls `rm -rf ~/Documents`",
    "cat <(rm -rf x)",
    'echo "expanded `rm -rf ~` here"',
    'echo "expanded $(rm -rf ~) here"',
]

# A separator inside quotes is literal text, not a second command. Warning
# fatigue is a real cost, so these must stay quiet.
QUOTED_SAFE = [
    'echo "a; rm -rf ~"',
    "echo 'x && rm -rf /'",
    "echo 'literal $(rm -rf ~)'",
    'grep "foo|bar" file.txt',
    "grep 'a; b' notes.md",
]


class TestChainedCommands(unittest.TestCase):
    """A read-only command at the START of the line must not excuse the rest."""

    def test_destructive_after_a_safe_prefix_is_flagged(self):
        for cmd in CHAINED_DESTRUCTIVE:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(danger.check(cmd), f"missed: {cmd}")

    def test_separators_inside_quotes_are_not_commands(self):
        for cmd in QUOTED_SAFE:
            with self.subTest(cmd=cmd):
                self.assertIsNone(danger.check(cmd), f"false alarm: {cmd}")

    def test_sudo_ls_does_not_excuse_rm_rf_root(self):
        """The case that made this worth fixing."""
        self.assertIsNone(danger.check("sudo ls"))
        self.assertIsNotNone(danger.check("sudo ls; rm -rf /"))

    def test_harm_reported_is_the_destructive_segment(self):
        self.assertIn("recursively deletes", danger.check("ls -la; rm -rf ~/x"))

    def test_single_quotes_suppress_substitution(self):
        """Single quotes are literal in shell; double quotes are not."""
        self.assertIsNone(danger.check("echo 'x $(rm -rf ~)'"))
        self.assertIsNotNone(danger.check('echo "x $(rm -rf ~)"'))


class TestSegments(unittest.TestCase):
    def test_splits_on_each_separator(self):
        self.assertEqual(danger.segments("a; b && c || d | e & f"),
                         ["a", "b", "c", "d", "e", "f"])

    def test_quoted_separator_is_not_a_split(self):
        self.assertEqual(danger.segments('echo "a; b"'), ['echo "a; b"'])

    def test_substitution_becomes_its_own_segment(self):
        self.assertEqual(danger.segments("ls $(rm -rf ~)"), ["rm -rf ~", "ls"])

    def test_nested_substitution(self):
        self.assertEqual(danger.segments("a $(b $(c))"), ["c", "b", "a"])

    def test_redirect_stays_with_its_command(self):
        """`>` is part of a command, not a separator — the truncation rule needs it."""
        self.assertEqual(danger.segments("echo x > f.txt"), ["echo x > f.txt"])

    def test_empty_and_whitespace(self):
        self.assertEqual(danger.segments(""), [])
        self.assertEqual(danger.segments("  ;  ;  "), [])


if __name__ == "__main__":
    unittest.main()
