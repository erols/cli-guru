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


if __name__ == "__main__":
    unittest.main()
