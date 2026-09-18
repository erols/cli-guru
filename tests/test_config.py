import os
import unittest
from unittest import mock

from cli_guru import config


class TestNormaliseHost(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("192.168.1.5:11434", "http://192.168.1.5:11434"),
            ("http://localhost", "http://localhost:11434"),
            ("http://localhost:11434/", "http://localhost:11434"),
            ("localhost", "http://localhost:11434"),
            ("https://box:443", "https://box:443"),
        ]
        for raw, want in cases:
            with self.subTest(raw=raw):
                self.assertEqual(config.normalise_host(raw), want)


class TestSimpleToml(unittest.TestCase):
    def test_flat_scalars(self):
        text = 'model = "x:4b"\nthink = false\ntimeout = 30 # seconds\n# comment\n[section]\n'
        self.assertEqual(
            config._parse_simple_toml(text), {"model": "x:4b", "think": False, "timeout": 30}
        )

    def test_ignores_junk(self):
        self.assertEqual(config._parse_simple_toml("nonsense\n\n"), {})


class TestPrecedence(unittest.TestCase):
    def test_env_beats_file_default(self):
        with mock.patch.object(config, "_load_file", return_value={"model": "from-file"}):
            with mock.patch.dict(os.environ, {"CLI_GURU_MODEL": "from-env"}):
                self.assertEqual(config.load()["model"], "from-env")

    def test_cli_beats_env(self):
        with mock.patch.object(config, "_load_file", return_value={}):
            with mock.patch.dict(os.environ, {"CLI_GURU_MODEL": "from-env"}):
                self.assertEqual(config.load({"model": "from-cli"})["model"], "from-cli")

    def test_none_override_ignored(self):
        with mock.patch.object(config, "_load_file", return_value={}):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(config.load({"model": None})["model"], config.DEFAULTS["model"])

    def test_bool_env_coerced(self):
        with mock.patch.object(config, "_load_file", return_value={}):
            with mock.patch.dict(os.environ, {"CLI_GURU_THINK": "true"}):
                self.assertIs(config.load()["think"], True)


class TestSimpleTomlComments(unittest.TestCase):
    """The <3.11 fallback parser must handle the config this project documents.

    CLAUDE.md and the README both show quoted values with trailing comments.
    Mishandling them produced a model name of `"qwen2.5-coder:1.5b"  # beats
    :3b`, which ollama answers with a 404 — a broken first run for anyone on
    Python 3.9 or 3.10, caused by following our own documentation.
    """

    def test_trailing_comment_after_quoted_value(self):
        parsed = config._parse_simple_toml('model = "qwen2.5-coder:1.5b"  # beats :3b\n')
        self.assertEqual(parsed["model"], "qwen2.5-coder:1.5b")

    def test_hash_inside_quotes_is_kept(self):
        """Splitting on "#" before honouring quotes would truncate this."""
        parsed = config._parse_simple_toml('host = "http://h/p#anchor"\n')
        self.assertEqual(parsed["host"], "http://h/p#anchor")

    def test_documented_defaults_round_trip(self):
        """Every key in the documented block must parse to its real default."""
        block = """
        model = "qwen2.5-coder:1.5b"  # beats :3b on both benchmarks
        keep_alive = "8h"             # -1 pins it
        think = false                 # ask mode
        timeout = 20                  # seconds
        """
        parsed = config._parse_simple_toml(block)
        self.assertEqual(parsed["model"], config.DEFAULTS["model"])
        self.assertEqual(parsed["keep_alive"], config.DEFAULTS["keep_alive"])
        self.assertEqual(parsed["think"], config.DEFAULTS["think"])
        self.assertEqual(parsed["timeout"], config.DEFAULTS["timeout"])

    def test_unterminated_quote_does_not_crash(self):
        self.assertEqual(config._parse_simple_toml('model = "oops\n')["model"], "oops")


if __name__ == "__main__":
    unittest.main()
