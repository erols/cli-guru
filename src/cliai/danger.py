"""Deterministic detection of destructive commands.

This is a SAFETY feature, so it must not depend on the model noticing. Measured:
qwen2.5-coder:3b missed 12 of 15 destructive commands when the warning was left
to the prompt, including `rm -rf /var/log/*`. cliai decides this itself and
prints the banner; the model only writes the explanation underneath.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# (pattern, what is lost). Ordered most-specific first.
_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r":\s*\(\s*\)\s*\{.*\|\s*:\s*&.*\}\s*;\s*:"),
     "fork bomb — this will hang the machine until it is rebooted"),
    (re.compile(r"\bmkfs(\.\w+)?\b"),
     "formats the filesystem — every file on that device is destroyed"),
    (re.compile(r"\bdd\b[^|]*\bof=/dev/"),
     "writes directly over a block device — its entire contents are destroyed"),
    (re.compile(r"\bshred\b"), "overwrites files so they cannot be recovered"),
    (re.compile(r"\brm\b[^|]*\s-[a-zA-Z]*[rR][a-zA-Z]*f|\brm\b[^|]*\s-[a-zA-Z]*f[a-zA-Z]*[rR]"),
     "recursively deletes without prompting — there is no undo and no trash"),
    (re.compile(r"\brm\b(?![^|]*\s-[a-zA-Z]*i)"),
     "deletes files permanently — there is no trash"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"),
     "discards all uncommitted changes in the working tree"),
    (re.compile(r"\bgit\s+clean\b[^|]*-[a-zA-Z]*f"),
     "deletes untracked files, which are not recoverable from git"),
    (re.compile(r"\bgit\s+push\b[^|]*(--force(?!-with-lease)|\s-f\b)"),
     "overwrites the remote branch — commits on it can be lost for everyone"),
    (re.compile(r"\btruncate\b[^|]*-s\s*0"), "empties the file — its contents are lost"),
    (re.compile(r"\bfind\b[^|]*-delete\b"), "deletes every matching file"),
    (re.compile(r"\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b", re.I),
     "drops database objects and the data in them"),
    (re.compile(r"\bdocker\s+(system\s+prune|volume\s+rm)\b"),
     "removes docker data, including volumes that may hold the only copy"),
    (re.compile(r"\b(chmod|chown)\b[^|]*\s-[a-zA-Z]*R[a-zA-Z]*\s+[^|]*\s/(?:\s|$)"),
     "recursively changes ownership or permissions from the filesystem root"),
    (re.compile(r"(?<![>\d])>(?!>)\s*(?!/dev/null)[\w./~-]+"),
     "the `>` redirect truncates the target file before writing"),
    (re.compile(r"\bmv\b[^|]*\s-[a-zA-Z]*f"), "overwrites the destination without prompting"),
]

# Commands that only read. The exemption is withdrawn the moment the line also
# does something destructive: `find . -exec rm {} +` is a delete wearing a
# read-only command's name.
_SAFE = re.compile(
    r"^\s*(?:sudo\s+|env\s+\S+=\S+\s+)*"
    r"(?:ls|ll|cat|less|more|head|tail|grep|rg|find|df|du|ps|top|"
    r"git\s+(?:log|status|diff|show|branch)|tar\s+-[a-zA-Z]*t|echo|printf|which|man)\b"
)
_ALWAYS_UNSAFE = re.compile(
    r">(?!>)\s*(?!/dev/null)|(?<![\w-])-delete\b|-exec\s+(?:rm|shred|truncate)\b|"
    r"\|\s*xargs\s+(?:-[^|]*\s+)?(?:rm|shred)\b"
)


def check(command: str) -> Optional[str]:
    """Return a warning sentence for a destructive command, else None."""
    if not command or not command.strip():
        return None
    line = command.strip()
    for pattern, harm in _RULES:
        if pattern.search(line):
            # A read-only command that merely contains a scary word is not a risk,
            # but a redirect or an explicit delete always is.
            if _SAFE.match(line) and not _ALWAYS_UNSAFE.search(line):
                return None
            return harm
    return None


def banner(command: str) -> Optional[str]:
    harm = check(command)
    return f"WARNING: {harm}" if harm else None
