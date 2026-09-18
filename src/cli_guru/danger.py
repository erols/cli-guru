"""Deterministic detection of destructive commands.

This is a SAFETY feature, so it must not depend on the model noticing. Measured:
qwen2.5-coder:3b missed 12 of 15 destructive commands when the warning was left
to the prompt, including `rm -rf /var/log/*`. cli-guru decides this itself and
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
# Withdraws the _SAFE exemption WITHIN a single segment: `find . -exec rm {} +`
# starts with an allowlisted command but is a delete. Cross-command cases like
# `ls; rm -rf ~` are handled by segmenting instead, not here.
_ALWAYS_UNSAFE = re.compile(
    r">(?!>)\s*(?!/dev/null)|(?<![\w-])-delete\b|-exec\s+(?:rm|shred|truncate)\b|"
    r"\bxargs\s+(?:-\S+\s+)*(?:rm|shred)\b"
)

# Separators that end one command and begin another. `>` is deliberately absent:
# a redirect is part of the command it belongs to.
_SEPARATORS = ";\n&|"


def _read_substitution(line: str, start: int, closer: str) -> Tuple[str, int]:
    """Read a command substitution body, returning (body, index after closer)."""
    depth = 1
    out: List[str] = []
    i = start
    while i < len(line):
        ch = line[i]
        if closer == ")" and ch == "(":
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return "".join(out), i + 1
        out.append(ch)
        i += 1
    return "".join(out), i


def segments(line: str) -> List[str]:
    """Split a command line into independently-judged commands.

    A warning must never be suppressed because the line merely *starts* with
    something read-only: `sudo ls; rm -rf /` is a delete, and judging the line
    as a whole silently cleared it. Substitutions are judged too, so the `rm` in
    `ls $(rm -rf ~)` is seen. Quoted text is never split, so `echo "a; b"` stays
    one command.
    """
    out: List[str] = []
    buf: List[str] = []
    quote = ""
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        # Single quotes are literal in shell: nothing expands inside them.
        if quote == "'":
            if ch == quote:
                quote = ""
            buf.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(line[i + 1])
            i += 2
            continue
        # Substitutions expand even inside double quotes, so these are checked
        # before the quote state: `echo "`rm -rf ~`"` really does delete.
        if ch == "`":
            body, i = _read_substitution(line, i + 1, "`")
            out.extend(segments(body))
            continue
        if ch in "$<>" and i + 1 < n and line[i + 1] == "(":
            body, i = _read_substitution(line, i + 2, ")")
            out.extend(segments(body))
            continue
        if quote == '"':
            if ch == quote:
                quote = ""
            buf.append(ch)
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch in _SEPARATORS:
            out.append("".join(buf))
            buf = []
            i += 2 if i + 1 < n and line[i + 1] == ch else 1  # && and || are one separator
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return [s.strip() for s in out if s.strip()]


def _check_segment(segment: str) -> Optional[str]:
    for pattern, harm in _RULES:
        if not pattern.search(segment):
            continue
        # A read-only command that merely contains a scary word is not a risk,
        # but a redirect or an explicit delete always is. Keep looking rather
        # than clearing the segment: an exemption earned against one rule must
        # not mask a different rule that also fires.
        if _SAFE.match(segment) and not _ALWAYS_UNSAFE.search(segment):
            continue
        return harm
    return None


def check(command: str) -> Optional[str]:
    """Return a warning sentence for a destructive command, else None.

    Every segment of the line is judged separately — see `segments`.
    """
    if not command or not command.strip():
        return None
    for segment in segments(command):
        harm = _check_segment(segment)
        if harm:
            return harm
    return None


def banner(command: str) -> Optional[str]:
    harm = check(command)
    return f"WARNING: {harm}" if harm else None
