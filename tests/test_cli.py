"""End-to-end CLI tests with the backend faked. No model is contacted."""

import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from cli_guru import cli
from cli_guru.backend import BackendError


class _TtyStringIO(io.StringIO):
    """Captures stdout while still reporting as a terminal, so the tty-only
    decoration paths are reachable under redirect_stdout."""

    def isatty(self):
        return True


def run(argv, content="ls -la", error=None, tty=False):
    out = _TtyStringIO() if tty else io.StringIO()
    err = io.StringIO()
    models = []

    class Fake:
        def __init__(self, *a, **k):
            models.append(a[1] if len(a) > 1 else k.get("model"))

        def chat(self, *a, **k):
            if error:
                raise error
            return content, "some reasoning"

        def check(self):
            if error:
                raise error
            return "ok: fake"

    # The spinner writes to /dev/tty, which during a test run is the developer's
    # own terminal. Stub it so the suite stays silent and these tests stay about
    # stdout/stderr; ui.Activity itself is covered in test_ui.py.
    with mock.patch.object(cli, "OllamaBackend", Fake), \
            mock.patch.object(cli.ui, "Activity", _NoActivity):
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
    run.models = models
    return code, out.getvalue(), err.getvalue()


class _NoActivity:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class AskTestCase(unittest.TestCase):
    def test_prints_only_the_command(self):
        code, out, err = run(["ask", "list", "files"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "ls -la")
        self.assertEqual(err, "")

    def test_fenced_output_is_cleaned(self):
        _, out, _ = run(["ask", "x"], content="```bash\nls -la\n```")
        self.assertEqual(out.strip(), "ls -la")

    def test_unusable_output_fails_with_empty_stdout(self):
        """The shell widget keys off empty stdout to leave the buffer alone."""
        code, out, err = run(["ask", "x"], content="Sorry, I cannot help with that.\n\n\n")
        self.assertEqual(out.strip(), "")
        self.assertEqual(code, 1)

    def test_backend_error_goes_to_stderr_not_stdout(self):
        code, out, err = run(["ask", "x"], error=BackendError("no ollama at http://h"))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("no ollama", err)

    def test_degenerate_repetition_rejected(self):
        code, out, _ = run(["ask", "x"], content="git " + "--quiet " * 40)
        self.assertEqual(out.strip(), "")
        self.assertEqual(code, 1)


class ArgumentTestCase(unittest.TestCase):
    def test_user_flags_are_not_claimed_by_argparse(self):
        """`cli-guru explain ls -la` must not die with 'unrecognized arguments'."""
        code, out, _ = run(["explain", "ls", "-la"], content="Lists files.")
        self.assertEqual(code, 0)

    def test_double_dash_is_stripped(self):
        code, out, _ = run(["ask", "--", "list files"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "ls -la")

    def test_leading_dash_question_survives(self):
        code, out, _ = run(["explain", "--", "tar -xzvf a.tgz"], content="Extracts.")
        self.assertEqual(code, 0)


class ExplainTestCase(unittest.TestCase):
    def test_prints_prose(self):
        code, out, _ = run(["explain", "ls", "-la"], content="Lists files.\n-l long format")
        self.assertEqual(code, 0)
        self.assertIn("long format", out)

    def test_empty_input_errors(self):
        code, out, err = run(["explain"])
        self.assertEqual(code, 1)
        self.assertIn("nothing to explain", err)


class CheckTestCase(unittest.TestCase):
    def test_check_alias_maps_to_subcommand(self):
        code, out, _ = run(["--check"])
        self.assertEqual(code, 0)
        self.assertIn("ok", out)

    def test_check_failure_is_actionable(self):
        code, _, err = run(["check"], error=BackendError("model 'x' not pulled"))
        self.assertEqual(code, 1)
        self.assertIn("not pulled", err)


class DebugTestCase(unittest.TestCase):
    def test_thinking_goes_to_stderr_never_stdout(self):
        code, out, err = run(["--debug", "ask", "x"])
        self.assertEqual(out.strip(), "ls -la")
        self.assertIn("some reasoning", err)
        self.assertNotIn("some reasoning", out)


class _Tty(io.StringIO):
    """Stands in for /dev/tty. Keeps its buffer readable after the with-block."""

    def close(self):  # noqa: D102 - deliberately does not discard the buffer
        pass


class EmptyAskTestCase(unittest.TestCase):
    """An empty `ask` must not prompt on stdout.

    stdout IS the readline buffer — the widget runs `out=$(cli-guru ask ...)` —
    so a prompt written there is swallowed by the capture and the terminal hangs
    on input the user cannot see they owe. Found by pressing the key on an empty
    line at a real prompt.
    """

    def _fake_tty(self, answer="list files by size"):
        self.opened = []
        self.writer, self.reader = _Tty(), _Tty(answer + "\n")

        def fake_open(path, mode="r", *a, **k):
            self.opened.append((str(path), mode))
            return self.writer if "w" in mode else self.reader

        return fake_open

    def test_prompt_goes_to_the_terminal_never_to_stdout(self):
        out = io.StringIO()  # not a tty, exactly like the widget's capture
        with redirect_stdout(out), mock.patch("builtins.open", self._fake_tty()):
            got = cli._read_question()
        self.assertEqual(got, "list files by size")
        self.assertEqual(out.getvalue(), "", "prompt leaked into the readline buffer")
        self.assertIn("cli-guru>", self.writer.getvalue())

    def test_tty_is_not_opened_read_write(self):
        """`open("/dev/tty", "r+")` raises UnsupportedOperation — a character
        device is not seekable — and that subclasses OSError, so it would be
        caught and silently look like "no terminal"."""
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("builtins.open", self._fake_tty()):
            cli._read_question()
        self.assertTrue(self.opened, "never opened the terminal")
        for path, mode in self.opened:
            self.assertEqual(path, "/dev/tty")
            self.assertNotIn("+", mode, f"opened /dev/tty as {mode!r}; must not be read-write")

    def test_no_terminal_reports_instead_of_blocking(self):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("builtins.open", side_effect=OSError("no tty")):
            self.assertIsNone(cli._read_question())

    def test_direct_use_with_a_tty_uses_plain_input(self):
        """Run straight from a shell, stdout is the terminal and input() is fine."""
        with mock.patch.object(cli.sys, "stdout") as fake_stdout, \
                mock.patch.object(cli, "input", create=True, return_value="  ls -la  "):
            fake_stdout.isatty.return_value = True
            self.assertEqual(cli._read_question(), "ls -la")

    def test_unanswerable_ask_exits_1_with_empty_stdout(self):
        """The widget keys off empty stdout, so the user's line is left alone."""
        with mock.patch.object(cli, "_read_question", return_value=None):
            code, out, err = run(["ask"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("type your question on the line first", err)


class ExplainDelimiterTestCase(unittest.TestCase):
    """Fence the answer off from whatever is already on screen — but only for a
    human. `cli-guru explain ... > notes.md` must stay plain prose."""

    def test_no_rules_when_piped(self):
        _, out, _ = run(["explain", "ls", "-la"], content="lists files")
        self.assertNotIn("####", out)
        self.assertEqual(out.strip(), "lists files")

    def test_rules_and_command_shown_at_a_terminal(self):
        _, out, _ = run(["explain", "tar", "-xzvf", "f.tgz"], content="extracts it", tty=True)
        self.assertIn("tar -xzvf f.tgz", out)
        self.assertTrue(out.startswith("####"))
        self.assertTrue(out.rstrip().endswith("#"))
        self.assertIn("extracts it", out)

    def test_warning_sits_inside_the_fence(self):
        _, out, _ = run(["explain", "git", "reset", "--hard"], content="resets", tty=True)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertTrue(lines[0].startswith("####"))
        self.assertTrue(lines[1].startswith("WARNING:"))
        self.assertTrue(lines[-1].startswith("####"))


class PerModeModelTestCase(unittest.TestCase):
    """explain may use a bigger model than ask.

    explain already has a 45s timeout against ask's 20s and runs ~8s anyway,
    whereas ask is the ~200ms path a keypress waits on. Measured: 1.5b invented
    a `-s` flag for `sudo apt install ./x.deb`, then invented dpkg and `-i`;
    7b was correct. Off by default — the cost is holding both models resident.
    """

    def test_defaults_to_one_model_for_both_modes(self):
        run(["ask", "x"])
        self.assertEqual(run.models, ["qwen2.5-coder:1.5b"])
        run(["explain", "ls"])
        self.assertEqual(run.models, ["qwen2.5-coder:1.5b"])

    def test_explain_uses_model_explain_when_set(self):
        with mock.patch.dict(os.environ, {"CLI_GURU_MODEL_EXPLAIN": "big:7b"}):
            run(["explain", "ls"])
            self.assertEqual(run.models, ["big:7b"])

    def test_ask_is_unaffected_by_model_explain(self):
        """The whole point is that the keypress path stays fast."""
        with mock.patch.dict(os.environ, {"CLI_GURU_MODEL_EXPLAIN": "big:7b"}):
            run(["ask", "x"])
            self.assertEqual(run.models, ["qwen2.5-coder:1.5b"])

    def test_explicit_flag_governs_both_modes(self):
        """--model must not be quietly ignored by a configured model_explain."""
        with mock.patch.dict(os.environ, {"CLI_GURU_MODEL_EXPLAIN": "big:7b"}):
            run(["--model", "chosen:1b", "explain", "ls"])
            self.assertEqual(run.models, ["chosen:1b"])

    def test_check_verifies_both_models_when_they_differ(self):
        """A second model is a second way to break, and it would only show up on
        an explain keypress."""
        with mock.patch.dict(os.environ, {"CLI_GURU_MODEL_EXPLAIN": "big:7b"}):
            _, out, _ = run(["check"])
        self.assertEqual(run.models, ["qwen2.5-coder:1.5b", "big:7b"])
        self.assertIn("explain model big:7b", out)

    def test_check_does_not_double_report_one_model(self):
        _, out, _ = run(["check"])
        self.assertNotIn("explain model", out)


if __name__ == "__main__":
    unittest.main()
