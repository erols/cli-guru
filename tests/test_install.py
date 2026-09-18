import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli_guru import install

ORIGINAL = 'export PATH=/usr/bin\nalias ll="ls -l"\n'


class InstallTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rc = Path(self.tmp.name) / ".bashrc"
        self.rc.write_text(ORIGINAL)
        self.script = Path("/opt/cliai/cliai.bash")
        patcher = mock.patch.object(install, "rc_path", lambda shell: self.rc)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def _install(self):
        rc, current, new = install.plan("bash", self.script)
        install.write(rc, current, new)

    def test_adds_marker_block(self):
        self._install()
        text = self.rc.read_text()
        self.assertIn(install.BEGIN, text)
        self.assertIn(install.END, text)
        self.assertIn(str(self.script), text)

    def test_preserves_existing_content(self):
        self._install()
        self.assertIn('alias ll="ls -l"', self.rc.read_text())

    def test_idempotent(self):
        self._install()
        first = self.rc.read_text()
        self._install()
        self._install()
        self.assertEqual(self.rc.read_text(), first)
        self.assertEqual(self.rc.read_text().count(install.BEGIN), 1)

    def test_uninstall_restores_byte_identical(self):
        self._install()
        rc, current, new = install.uninstall_plan("bash")
        install.write(rc, current, new, backup=False)
        self.assertEqual(self.rc.read_text(), ORIGINAL)

    def test_backup_made_once(self):
        self._install()
        backup = self.rc.with_suffix(self.rc.suffix + ".cliai.bak")
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(), ORIGINAL)
        self._install()
        self.assertEqual(backup.read_text(), ORIGINAL)

    def test_missing_rc_file_is_created(self):
        self.rc.unlink()
        self._install()
        self.assertIn(install.BEGIN, self.rc.read_text())

    def test_file_without_trailing_newline(self):
        self.rc.write_text("export A=1")
        self._install()
        self.assertIn("export A=1\n# >>> cliai >>>", self.rc.read_text())

    def test_dry_run_diff_writes_nothing(self):
        rc, current, new = install.plan("bash", self.script)
        diff = install.diff(rc, current, new)
        self.assertIn("+# >>> cliai >>>", diff)
        self.assertEqual(self.rc.read_text(), ORIGINAL)

    def test_strip_block_handles_absent_block(self):
        self.assertEqual(install.strip_block(ORIGINAL), ORIGINAL)


class ShellDetectionTestCase(unittest.TestCase):
    def test_powershell_block_uses_dot_sourcing(self):
        block = install.block_for("powershell", Path("C:/x/cliai.ps1"))
        self.assertIn("Test-Path", block)

    def test_posix_block_guards_on_file_existing(self):
        block = install.block_for("bash", Path("/x/cliai.bash"))
        self.assertIn("[ -f", block)


if __name__ == "__main__":
    unittest.main()
