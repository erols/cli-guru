"""Ground `explain` in the real man page rather than model memory."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

# Wrappers to skip when finding the command actually being run.
_WRAPPERS = {
    "sudo", "doas", "env", "time", "nice", "nohup", "xargs", "command",
    "builtin", "exec", "watch", "timeout", "stdbuf",
}
# Tools whose real documentation lives in `man <tool>-<subcommand>`.
_SUBCOMMAND_TOOLS = {
    "git", "docker", "kubectl", "systemctl", "apt", "npm", "cargo", "go",
    "pip", "podman", "zfs", "ip",
}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_OVERSTRIKE = re.compile(r".\x08")
_SECTION = re.compile(r"^(?P<name>[A-Z][A-Z0-9 /'-]{2,})\s*$")

# Kept in priority order when the page must be trimmed.
_KEEP_FIRST = ["NAME", "SYNOPSIS", "OPTIONS", "FLAGS", "DESCRIPTION", "EXAMPLES"]
_DROP_FIRST = [
    "AUTHOR", "AUTHORS", "BUGS", "REPORTING BUGS", "SEE ALSO", "HISTORY",
    "COPYRIGHT", "COLOPHON", "NOTES", "STANDARDS", "AVAILABILITY", "TRANSLATION",
]


def base_command(line: str) -> Tuple[str, Optional[str]]:
    """Return (command, subcommand) for a command line, skipping wrappers.

    >>> base_command("sudo FOO=1 git commit -m x")
    ('git', 'commit')
    """
    tokens = line.strip().split()
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if _ASSIGNMENT.match(token) or token in _WRAPPERS:
            idx += 1
            continue
        break
    if idx >= len(tokens):
        return "", None
    cmd = os.path.basename(tokens[idx])
    sub = None
    if cmd in _SUBCOMMAND_TOOLS and idx + 1 < len(tokens):
        candidate = tokens[idx + 1]
        if not candidate.startswith("-"):
            sub = candidate
    return cmd, sub


def _strip_overstrike(text: str) -> str:
    """Equivalent of `col -b`, without needing col to exist."""
    return _OVERSTRIKE.sub("", text)


def _run(cmd: List[str], timeout: float = 5.0) -> Optional[str]:
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "LANG": "C", "LC_ALL": "C", "MANWIDTH": "80", "PAGER": "cat"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0 or not res.stdout.strip():
        return None
    return _strip_overstrike(res.stdout)


def split_sections(text: str) -> List[Tuple[str, str]]:
    """Split a man page into (SECTION, body) pairs, preserving order."""
    sections: List[Tuple[str, List[str]]] = []
    current = "HEADER"
    buf: List[str] = []
    for line in text.splitlines():
        match = _SECTION.match(line)
        if match:
            sections.append((current, buf))
            current = match.group("name").strip()
            buf = []
        else:
            buf.append(line)
    sections.append((current, buf))
    return [(name, "\n".join(body).strip("\n")) for name, body in sections]


def truncate(text: str, limit: int) -> str:
    """Trim to `limit` chars while KEEPING the options section.

    Naive head-truncation discards the only part that answers "what does this
    flag do", which is the entire point of explain mode.
    """
    if len(text) <= limit:
        return text
    sections = split_sections(text)
    if len(sections) <= 1:
        return text[:limit] + "\n... (truncated)"

    def score(name: str) -> int:
        upper = name.upper()
        for i, keep in enumerate(_KEEP_FIRST):
            if keep in upper:
                return i
        if any(drop in upper for drop in _DROP_FIRST):
            return 100
        return 50

    ordered = sorted(range(len(sections)), key=lambda i: (score(sections[i][0]), i))
    chosen: List[int] = []
    total = 0
    for i in ordered:
        name, body = sections[i]
        cost = len(name) + len(body) + 2
        if total + cost > limit:
            if score(name) == 0 and not chosen:
                chosen.append(i)
                total += cost
            continue
        chosen.append(i)
        total += cost
    chosen.sort()
    out = []
    for i in chosen:
        name, body = sections[i]
        out.append(body if name == "HEADER" else f"{name}\n{body}")
    result = "\n\n".join(out).strip()
    if len(result) > limit:
        result = result[:limit] + "\n... (truncated)"
    if len(chosen) < len(sections):
        result += "\n\n(some sections omitted)"
    return result


def fetch(
    cmd: str, sub: Optional[str] = None, *, run_help: bool = False
) -> Tuple[Optional[str], str]:
    """Return (text, source). `source` names where it came from, for the prompt.

    Reads documentation; it does NOT run the command being explained. You ask
    explain what a command does precisely because you have not run it yet — the
    "I pasted this from the internet" case — so executing it to find out
    inverts the whole point. `<cmd> --help` is therefore opt-in via `run_help`,
    and `-h` is never used at all: it is not universally "help" (`shutdown -h`
    halts; on BSD it commonly means "human readable" or "no-dereference").

    The cost of the default is small and lands in the right place. `man` answers
    for anything with a man page; the fallback only ever fired for commands
    WITHOUT one, which are exactly the unknown third-party binaries where
    running them is least acceptable. When nothing is found the caller must SAY
    the answer is ungrounded rather than pretend otherwise.
    """
    if not cmd:
        return None, "none"

    if platform.system() == "Windows":
        # Get-Help reads the help system; it does not invoke `cmd` itself.
        if shutil.which("powershell"):
            text = _run(["powershell", "-NoProfile", "-Command", f"Get-Help {cmd} -Full"])
            if text:
                return text, f"Get-Help {cmd}"
    elif shutil.which("man"):
        if sub:
            text = _run(["man", f"{cmd}-{sub}"])
            if text:
                return text, f"man {cmd}-{sub}"
        text = _run(["man", cmd])
        if text:
            return text, f"man {cmd}"

    if run_help and shutil.which(cmd):
        text = _run([cmd, "--help"], timeout=3.0)
        if text:
            return text, f"{cmd} --help"
    return None, "none"
