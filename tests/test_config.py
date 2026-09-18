import os
import unittest
from unittest import mock

from cliai import config


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
            with mock.patch.dict(os.environ, {"CLIAI_MODEL": "from-env"}):
                self.assertEqual(config.load()["model"], "from-env")

    def test_cli_beats_env(self):
        with mock.patch.object(config, "_load_file", return_value={}):
            with mock.patch.dict(os.environ, {"CLIAI_MODEL": "from-env"}):
                self.assertEqual(config.load({"model": "from-cli"})["model"], "from-cli")

    def test_none_override_ignored(self):
        with mock.patch.object(config, "_load_file", return_value={}):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(config.load({"model": None})["model"], config.DEFAULTS["model"])

    def test_bool_env_coerced(self):
        with mock.patch.object(config, "_load_file", return_value={}):
            with mock.patch.dict(os.environ, {"CLIAI_THINK": "true"}):
                self.assertIs(config.load()["think"], True)


if __name__ == "__main__":
    unittest.main()
