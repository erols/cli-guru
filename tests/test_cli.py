"""End-to-end CLI tests with the backend faked. No model is contacted."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from cli_guru import cli
from cli_guru.backend import BackendError


def run(argv, content="ls -la", error=None):
    out, err = io.StringIO(), io.StringIO()

    class Fake:
        def __init__(self, *a, **k):
            pass

        def chat(self, *a, **k):
            if error:
                raise error
            return content, "some reasoning"

        def check(self):
            if error:
                raise error
            return "ok: fake"

    with mock.patch.object(cli, "OllamaBackend", Fake):
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


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


if __name__ == "__main__":
    unittest.main()
