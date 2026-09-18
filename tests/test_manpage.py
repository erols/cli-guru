import unittest

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


if __name__ == "__main__":
    unittest.main()
