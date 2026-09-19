"""Terminal feedback tests.

The spinner exists because a keypress that shows nothing for several seconds is
indistinguishable from a hang. It must never reach stdout: for `ask`, stdout is
the readline buffer.
"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from cli_guru import ui


class _Tty(io.StringIO):
    encoding = "utf-8"

    def close(self):  # keep the buffer readable after the with-block
        pass


class ActivityTestCase(unittest.TestCase):
    def test_spinner_never_touches_stdout_or_stderr(self):
        tty = _Tty()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ui, "open_tty", return_value=tty):
            with redirect_stdout(out), redirect_stderr(err):
                with ui.Activity("thinking", interval=0.01):
                    import time

                    time.sleep(0.05)
        self.assertEqual(out.getvalue(), "", "spinner leaked into the readline buffer")
        self.assertEqual(err.getvalue(), "")
        self.assertIn("thinking", tty.getvalue())

    def test_line_is_erased_on_exit(self):
        """The answer must land on a clean row, and so must an error."""
        tty = _Tty()
        with mock.patch.object(ui, "open_tty", return_value=tty):
            with ui.Activity("thinking", interval=0.01):
                import time

                time.sleep(0.05)
        self.assertTrue(tty.getvalue().endswith("\r"), "spinner line was not erased")
        self.assertIn("   ", tty.getvalue(), "erase should blank the drawn width")

    def test_no_terminal_is_not_an_error(self):
        """Containers, cron, Windows: no spinner is cosmetic, a crash is not."""
        with mock.patch.object(ui, "open_tty", return_value=None):
            with ui.Activity("thinking", interval=0.01):
                pass  # must simply do nothing

    def test_exception_still_erases_and_propagates(self):
        tty = _Tty()
        with mock.patch.object(ui, "open_tty", return_value=tty):
            with self.assertRaises(ValueError):
                with ui.Activity("thinking", interval=0.01):
                    raise ValueError("boom")
        self.assertNotIn("Traceback", tty.getvalue())

    def test_ascii_fallback_when_terminal_cannot_encode_braille(self):
        """A C-locale terminal must not raise UnicodeEncodeError mid-spin."""
        tty = _Tty()
        tty.encoding = "ascii"
        self.assertEqual(ui._frames(tty), ui._FRAMES_ASCII)
        tty.encoding = "utf-8"
        self.assertEqual(ui._frames(tty), ui._FRAMES_UNICODE)


class RuleTestCase(unittest.TestCase):
    def test_open_rule_carries_the_command(self):
        line = ui.open_rule("tar -xzvf f.tgz")
        self.assertIn("tar -xzvf f.tgz", line)
        self.assertTrue(line.startswith("####"))

    def test_rules_match_width(self):
        self.assertEqual(len(ui.open_rule("ls")), len(ui.rule()))

    def test_hash_not_star(self):
        """`#` is a comment if it ever reaches a prompt; `*` is a glob."""
        self.assertNotIn("*", ui.rule())

    def test_overlong_title_does_not_wrap(self):
        line = ui.open_rule("x" * 200)
        self.assertEqual(len(line.splitlines()), 1)

    def test_tty_is_never_opened_read_write(self):
        seen = []

        def fake_open(path, mode="r", *a, **k):
            seen.append((path, mode))
            return _Tty()

        with mock.patch("builtins.open", fake_open):
            ui.open_tty("w")
            ui.open_tty("r")
        self.assertEqual([m for _, m in seen], ["w", "r"])
        for path, mode in seen:
            self.assertEqual(path, "/dev/tty")
            self.assertNotIn("+", mode)


if __name__ == "__main__":
    unittest.main()
