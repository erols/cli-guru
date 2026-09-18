"""Assemble cheap, bounded context about where the user is standing.

Never reads file contents. Never reads the process environment. Every
subprocess is capped with a timeout so a keypress cannot hang.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

# Presence-checked allowlist, so the model only suggests tools that exist here.
# Allowlist only — never enumerate $PATH.
TOOLS = [
    "rg", "fd", "jq", "git", "docker", "kubectl", "systemctl", "ss", "curl",
    "wget", "tar", "zip", "unzip", "rsync", "ffmpeg", "python3", "node", "awk",
]

# (pattern, replacement) pairs. Order matters: forms that carry a VALUE come
# first so the value is consumed too — a pattern matching only the key name
# leaves the secret sitting in the text.
_SECRET_PATTERNS = [
    # Authorization headers: redact the whole thing, scheme included.
    (re.compile(r"(?:authorization\s*:\s*)?\bbearer\s+\S+", re.IGNORECASE), "<redacted>"),
    # KEY=value / KEY: value, where the key name looks secret-ish.
    (re.compile(
        r"\b([\w.-]*(?:password|passwd|secret|token|api[_-]?key|access[_-]?key"
        r"|private[_-]?key|credential)[\w.-]*)\s*[=:]\s*\S+",
        re.IGNORECASE), r"\1=<redacted>"),
    # --password=x, --token x, --api-key x
    (re.compile(r"(--?(?:password|passwd|token|api[_-]?key|secret)[\w-]*)(?:[=\s]+\S+)?",
                re.IGNORECASE), r"\1=<redacted>"),
    # mysql-style attached password: -pSECRET (no space, so `-p 5432` is left alone).
    (re.compile(r"(-p)\S{6,}"), r"\1<redacted>"),
    # Bare AWS access key ids.
    (re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), "<redacted>"),
]


def _run(cmd: List[str], timeout: float = 2.0, cwd: Optional[str] = None) -> str:
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            env={**os.environ, "LANG": "C", "LC_ALL": "C"},
        )
        return res.stdout.strip() if res.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def redact(text: str) -> str:
    """Blank out secret-shaped fragments, INCLUDING their values, before they
    can enter a prompt."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def listing(cwd: Path, max_files: int) -> str:
    try:
        entries = sorted(
            os.scandir(cwd), key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())
        )
    except OSError:
        return "(unreadable)"
    names: List[str] = []
    for entry in entries:
        if len(names) >= max_files:
            names.append(f"... {len(entries) - max_files} more")
            break
        try:
            names.append(entry.name + "/" if entry.is_dir(follow_symlinks=False) else entry.name)
        except OSError:
            names.append(entry.name)
    return "  ".join(names) if names else "(empty)"


_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
              "target", "dist", "build", ".mypy_cache", ".pytest_cache"}


def file_types(cwd: Path, max_entries: int = 2000) -> str:
    """Recursive extension histogram.

    A top-level listing alone leaves the model blind: asked to "count lines of
    python in this project" with only `src/ tests/ CLAUDE.md` visible, it
    grepped CLAUDE.md. This is bounded and cheap, and fixes that class of miss.
    """
    counts: Dict[str, int] = {}
    seen = 0
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in files:
            seen += 1
            if seen > max_entries:
                break
            ext = Path(name).suffix.lower() or "(no ext)"
            counts[ext] = counts.get(ext, 0) + 1
        if seen > max_entries:
            break
    if not counts:
        return ""
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
    return " ".join(f"{n} {ext}" for ext, n in top)


def git_info(cwd: Path) -> str:
    if not _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(cwd)) == "true":
        return ""
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(cwd)) or "?"
    user = _run(["git", "config", "user.name"], cwd=str(cwd))
    porcelain = _run(["git", "status", "--porcelain"], cwd=str(cwd))
    who = f", user {user}" if user else ""
    if not porcelain:
        return f"git: on {branch}, clean{who}"
    staged = untracked = modified = 0
    for line in porcelain.splitlines():
        if line.startswith("??"):
            untracked += 1
        elif line[:1] not in (" ", ""):
            staged += 1
        else:
            modified += 1
    return (
        f"git: on {branch}, {staged} staged, {modified} modified, "
        f"{untracked} untracked{who}"
    )


def coreutils_flavour() -> str:
    """GNU vs BSD changes real flags (`sed -i`, `date`, `stat`, `find`).

    A command correct on Linux and silently wrong on macOS is this tool's most
    likely quality bug, so the flavour goes in the prompt.
    """
    if platform.system() == "Windows":
        return "windows"
    try:
        res = subprocess.run(
            ["sed", "--version"], capture_output=True, text=True, timeout=2.0
        )
        if res.returncode == 0 and "GNU" in res.stdout:
            return "GNU coreutils"
    except (OSError, subprocess.SubprocessError):
        pass
    return "BSD userland (macOS)" if platform.system() == "Darwin" else "non-GNU userland"


def os_name() -> str:
    system = platform.system()
    if system == "Linux":
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return "Linux"
    if system == "Darwin":
        ver = _run(["sw_vers", "-productVersion"])
        return f"macOS {ver}".strip()
    if system == "Windows":
        return "Windows " + (platform.win32_ver()[0] or "")
    return system or "unknown"


def history(limit: int) -> str:
    """Read from $CLI_GURU_HISTORY only.

    The shell adapter captures this with `fc -ln`, because a subprocess reading
    $HISTFILE sees a stale file that the interactive shell has not flushed.
    """
    raw = os.environ.get("CLI_GURU_HISTORY", "")
    if not raw:
        return ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return "\n".join(redact(ln) for ln in lines[-limit:])


def collect(cfg: Dict) -> Dict[str, str]:
    cwd = Path.cwd()
    try:
        display = "~/" + str(cwd.relative_to(Path.home()))
    except ValueError:
        display = str(cwd)
    present = [t for t in TOOLS if shutil.which(t)]
    return {
        "cwd": str(cwd),
        "cwd_display": display,
        "files": listing(cwd, int(cfg.get("max_files", 50))),
        "file_types": file_types(cwd),
        "git": git_info(cwd),
        "history": history(int(cfg.get("history_lines", 10))),
        "os": os_name(),
        "kernel": platform.release(),
        "shell": Path(os.environ.get("SHELL", "")).name or "unknown",
        "userland": coreutils_flavour(),
        "tools": " ".join(present),
    }


def render(ctx: Dict[str, str], include_tools: bool = False) -> str:
    parts = [
        f"System: {ctx['os']} (kernel {ctx['kernel']}), {ctx['userland']}, shell {ctx['shell']}",
        f"Working directory: {ctx['cwd_display']}",
        f"Files here: {ctx['files']}",
    ]
    if ctx.get("file_types"):
        parts.append(f"File types in tree: {ctx['file_types']}")
    if ctx.get("git"):
        parts.append(ctx["git"])
    # Off by default — see config.include_tools for the measurement.
    if include_tools and ctx.get("tools"):
        parts.append(f"Available tools: {ctx['tools']}")
    if ctx.get("history"):
        parts.append("Recent commands:\n" + ctx["history"])
    return "\n".join(parts)
