"""Dotfile integration.

A subcommand rather than a shell script, so it can be tested. Dotfile edits
happen ONLY here and only when the user runs `cliai install` — never as a side
effect of another command.
"""

from __future__ import annotations

import difflib
import os
import platform
import shutil
from pathlib import Path
from typing import Optional, Tuple

BEGIN = "# >>> cliai >>>"
END = "# <<< cliai <<<"

SHELL_FILES = {
    "bash": ("cliai.bash", "~/.bashrc"),
    "zsh": ("cliai.zsh", "~/.zshrc"),
    "powershell": ("cliai.ps1", None),  # resolved from $PROFILE
}


def detect_shell() -> str:
    if platform.system() == "Windows":
        return "powershell"
    name = Path(os.environ.get("SHELL", "")).name
    if name in ("zsh", "bash"):
        return name
    if platform.system() == "Darwin":
        return "zsh"  # macOS default since Catalina
    return "bash"


def rc_path(shell: str) -> Optional[Path]:
    if shell == "powershell":
        profile = os.environ.get("PROFILE")
        if profile:
            return Path(profile)
        return Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    _, rc = SHELL_FILES[shell]
    return Path(rc).expanduser() if rc else None


def block_for(shell: str, script: Path) -> str:
    if shell == "powershell":
        body = f'if (Test-Path "{script}") {{ . "{script}" }}'
    else:
        body = f'[ -f "{script}" ] && . "{script}"'
    return f"{BEGIN}\n{body}\n{END}\n"


def strip_block(text: str) -> str:
    """Remove an existing cliai block. Idempotent; leaves everything else byte-identical."""
    out = []
    skipping = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == BEGIN:
            skipping = True
            continue
        if stripped == END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "".join(out)


def plan(shell: str, script: Path) -> Tuple[Path, str, str]:
    """Return (rc_file, current_text, new_text) without writing anything."""
    rc = rc_path(shell)
    if rc is None:
        raise ValueError(f"no rc file known for shell {shell!r}")
    current = rc.read_text(encoding="utf-8", errors="replace") if rc.exists() else ""
    stripped = strip_block(current)
    if stripped and not stripped.endswith("\n"):
        stripped += "\n"
    new = stripped + block_for(shell, script)
    return rc, current, new


def diff(rc: Path, current: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=str(rc),
            tofile=str(rc) + " (after)",
        )
    ) or "(no change)"


def write(rc: Path, current: str, new: str, backup: bool = True) -> Optional[Path]:
    """Write `new`, backing up the original once. Returns the backup path if made."""
    made: Optional[Path] = None
    if backup and rc.exists():
        bak = rc.with_suffix(rc.suffix + ".cliai.bak")
        if not bak.exists():
            shutil.copy2(rc, bak)
            made = bak
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text(new, encoding="utf-8")
    return made


def uninstall_plan(shell: str) -> Tuple[Path, str, str]:
    rc = rc_path(shell)
    if rc is None:
        raise ValueError(f"no rc file known for shell {shell!r}")
    current = rc.read_text(encoding="utf-8", errors="replace") if rc.exists() else ""
    return rc, current, strip_block(current)
