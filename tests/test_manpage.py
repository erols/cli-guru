import unittest
from unittest import mock

from cli_guru import manpage

# A trimmed real-shaped man page. Checked in so tests never shell out to `man`,
# which differs between GNU and BSD and may be absent entirely.
FIXTURE = """\
TAR(1)                      General Commands Manual                     TAR(1)

NAME
       tar - an archiving utility

SYNOPSIS
       tar [OPTION...] [FILE]...

DESCRIPTION
       Tar stores and extracts files from a tape or disk archive.

OPTIONS
       -x, --extract
              Extract files from an archive.

       -z, --gzip
              Filter the archive through gzip.

       -f, --file=ARCHIVE
              Use archive file ARCHIVE.

AUTHOR
       Written by John Gilmore.

BUGS
       Report bugs to bug-tar@gnu.org.

SEE ALSO
       gzip(1), bzip2(1)

COPYRIGHT
       Copyright 2023 Free Software Foundation.
"""


class TestBaseCommand(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("tar -xzvf f.tgz", ("tar", None)),
            ("sudo git commit -m x", ("git", "commit")),
            ("FOO=1 env time /usr/bin/rsync -a a b", ("rsync", None)),
            ("git log --oneline", ("git", "log")),
            ("docker -v", ("docker", None)),
            ("kubectl get pods", ("kubectl", "get")),
            ("sudo  ", ("", None)),
            ("", ("", None)),
        ]
        for line, want in cases:
            with self.subTest(line=line):
                self.assertEqual(manpage.base_command(line), want)


class TestSections(unittest.TestCase):
    def test_splits_known_sections(self):
        names = [n for n, _ in manpage.split_sections(FIXTURE)]
        for expected in ("NAME", "SYNOPSIS", "DESCRIPTION", "OPTIONS", "AUTHOR", "BUGS"):
            self.assertIn(expected, names)


class TestTruncate(unittest.TestCase):
    def test_short_page_unchanged(self):
        self.assertEqual(manpage.truncate("short", 1000), "short")

    def test_keeps_options_drops_boilerplate(self):
        """The whole point of explain mode is the flags; naive head-truncation
        would keep the copyright notice and throw the OPTIONS section away."""
        out = manpage.truncate(FIXTURE, 400)
        self.assertIn("--extract", out)
        self.assertNotIn("Free Software Foundation", out)
        self.assertNotIn("bug-tar@gnu.org", out)

    def test_respects_limit(self):
        out = manpage.truncate(FIXTURE, 300)
        self.assertLessEqual(len(out), 300 + len("\n\n(some sections omitted)") + 20)


class TestOverstrike(unittest.TestCase):
    def test_strips_backspace_bolding(self):
        self.assertEqual(manpage._strip_overstrike("t\x08ta\x08ar\x08r"), "tar")


class TestFetchDoesNotExecute(unittest.TestCase):
    """explain must not run the command it was asked to explain.

    You reach for explain BEFORE running something — the "I pasted this from
    the internet" case — so a docs fallback that executes it inverts the point.
    No real subprocess runs here: `_run` is replaced with a recorder, which also
    keeps the suite honest on hosts with no `man` at all.
    """

    def setUp(self):
        self.calls = []

        def recorder(cmd, timeout=5.0):
            self.calls.append(list(cmd))
            return None  # nothing yields docs, so every fallback is attempted

        self._patches = [
            mock.patch.object(manpage, "_run", recorder),
            mock.patch.object(manpage.shutil, "which", lambda c: "/usr/bin/" + c),
            mock.patch.object(manpage.platform, "system", lambda: "Linux"),
        ]
        for pat in self._patches:
            pat.start()
            self.addCleanup(pat.stop)

    def test_default_never_invokes_the_command(self):
        text, source = manpage.fetch("frobnicate")
        self.assertIsNone(text)
        self.assertEqual(source, "none")
        self.assertEqual(self.calls, [["man", "frobnicate"]])

    def test_default_does_not_invoke_subcommand_tools_either(self):
        manpage.fetch("git", "commit")
        for call in self.calls:
            self.assertEqual(call[0], "man", f"executed the command: {call}")

    def test_run_help_is_opt_in(self):
        manpage.fetch("frobnicate", run_help=True)
        self.assertIn(["frobnicate", "--help"], self.calls)

    def test_dash_h_is_never_used(self):
        """`-h` is not universally help: `shutdown -h` halts, BSD uses it for
        "human readable" and "no-dereference"."""
        manpage.fetch("frobnicate", run_help=True)
        for call in self.calls:
            self.assertNotIn("-h", call, f"used -h: {call}")

    def test_man_still_preferred_over_help(self):
        with mock.patch.object(manpage, "_run", lambda cmd, timeout=5.0: "MAN TEXT"):
            text, source = manpage.fetch("tar", run_help=True)
        self.assertEqual(text, "MAN TEXT")
        self.assertEqual(source, "man tar")

    def test_missing_command_is_reported_not_guessed(self):
        """source 'none' is what makes cli.py say the answer is ungrounded."""
        self.assertEqual(manpage.fetch("frobnicate")[1], "none")


if __name__ == "__main__":
    unittest.main()
