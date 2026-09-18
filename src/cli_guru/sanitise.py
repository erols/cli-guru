"""Clean model output before it reaches a live shell prompt.

This is the highest-risk code in the project: `ask` output is written straight
into the user's readline buffer. Models emit fences and prose regardless of
instructions, so this runs unconditionally.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*$")
_PROMPT = re.compile(r"^\s*(?:\$|#|>|PS\s*>|[\w.@-]*[:~][^\s$#]*\s*[$#])\s+")
_COMMENTARY = re.compile(
    r"^\s*(?:here(?:'s| is)\b|you can\b|this (?:command|will)\b|to \w+ (?:this|that)\b|"
    r"sure\b|certainly\b|note:|explanation:|answer:|command:|"
    r"sorry\b|i'?m sorry\b|i can(?:no|')?t\b|i am unable\b|unable to\b|as an ai\b)",
    re.IGNORECASE,
)
# A sentence ends in punctuation preceded by letters ("... with that."), whereas
# a command ending in a dot has it as its own token ("cp x ."). That distinction
# is what keeps a refusal out of the user's prompt.
_SENTENCE = re.compile(r"[A-Za-z]{2}[.?!]$")


def strip_fences(text: str) -> str:
    """Remove markdown fences, keeping the fenced body."""
    lines = text.splitlines()
    kept = [ln for ln in lines if not _FENCE.match(ln)]
    return "\n".join(kept)


# A real command line is short. Anything past this is almost certainly a
# degenerate repetition loop, which must not reach the user's prompt.
MAX_COMMAND_CHARS = 400

# C0 control characters and DEL, minus tab. Newlines never survive splitlines(),
# so they are not listed. An ESC sequence in the readline buffer can redraw the
# line, so what you read before pressing Enter need not be what runs —
# `echo safe\x1b[2K\x1b[1G rm -rf ~` displays as one command and runs another.
# It also hides the rest of the line from danger.py. Reject rather than strip:
# a line needing this treatment is not a command we should be handing over.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# Whole escape sequences, for explain output. Dropping the lone ESC byte would
# neutralise the sequence but leave its parameters as visible litter ("[1mtext").
# Covers CSI (\x1b[...), OSC (\x1b]... terminated by BEL or ST) and the short
# two-character escapes.
_ANSI = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI: colours, cursor moves, erases
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC: window title, clipboard
    r"|\x1b[@-Z\\-_]"                      # two-character escapes
)


def _is_prose(line: str) -> bool:
    """Reject model prose that is not a command.

    Without this, "Sorry, I cannot help with that." is pasted into a live prompt.
    """
    return bool(_SENTENCE.search(line)) and len(line.split()) >= 4


def _degenerate(line: str) -> bool:
    """Detect repetition loops like `--quiet --quiet --quiet ...`."""
    if len(line) > MAX_COMMAND_CHARS:
        return True
    tokens = line.split()
    if len(tokens) >= 8:
        counts = {}
        for tok in tokens:
            counts[tok] = counts.get(tok, 0) + 1
        if max(counts.values()) / len(tokens) > 0.5:
            return True
    return False


def command(text: str) -> str:
    """Reduce model output to a single runnable command line.

    Returns "" when nothing usable survives — callers must treat that as failure
    and leave the user's buffer untouched.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = strip_fences(text)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _COMMENTARY.match(line):
            continue
        line = _PROMPT.sub("", line).strip()
        # A whole line wrapped in backticks, or stray leading/trailing ones.
        if line.startswith("`") and line.endswith("`") and len(line) > 1:
            line = line[1:-1].strip()
        line = line.strip("`").strip()
        if not line:
            continue
        if _COMMENTARY.match(line):
            continue
        if _degenerate(line) or _is_prose(line) or _CONTROL.search(line):
            return ""
        return line
    return ""


# Models emit markdown for explain no matter what the prompt says; smaller ones
# are the worst offenders (qwen2.5-coder:1.5b writes `**--oneline**:` bullets).
# It is noise at a terminal prompt, so strip it rather than fight it in the prompt.
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.S)
_MD_BULLET = re.compile(r"^\s*[-*+]\s+", re.M)
_MD_HEADING = re.compile(r"^\s*#{1,6}\s*", re.M)
_MD_TICK = re.compile(r"`([^`]+)`")


def prose(text: str) -> str:
    """Clean explain output for a terminal: no fences, no markdown, no blank runs.

    Control characters are stripped rather than rejected: this text is printed,
    never executed, so losing an escape sequence costs nothing while a discarded
    explanation costs the user their answer.
    """
    text = _CONTROL.sub("", _ANSI.sub("", strip_fences(text or "")))
    text = _MD_BOLD.sub(lambda m: m.group(1) or m.group(2) or "", text)
    text = _MD_TICK.sub(r"\1", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_BULLET.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
