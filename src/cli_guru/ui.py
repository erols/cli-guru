"""Terminal feedback: the spinner and the delimiters around explain output.

Everything here writes to **/dev/tty**, never to stdout or stderr, and that is
not a stylistic choice:

- stdout is the readline buffer. The shell widget runs `out=$(cli-guru ask ...)`,
  so anything printed there is captured and pasted into the user's prompt.
- stderr is redirected to a temp file by the adapter and printed only after the
  command exits — exactly when a progress indicator has stopped being useful.

/dev/tty is the only channel the user is looking at while the model is working.
When it cannot be opened (Windows, containers, some ssh/tmux, a cron job) every
function here degrades to doing nothing, because a missing spinner is a
cosmetic loss and a crashed keypress is not.
"""

from __future__ import annotations

import shutil
import threading
from typing import Optional, TextIO

# Braille frames read as motion at small sizes, but a terminal in the C locale
# cannot encode them. Fall back rather than raise UnicodeEncodeError mid-spin.
_FRAMES_UNICODE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_FRAMES_ASCII = "|/-\\"

MAX_RULE = 72


def open_tty(mode: str = "w") -> Optional[TextIO]:
    """Open the controlling terminal, or return None if there isn't one.

    Always one mode at a time: /dev/tty is a character device and is not
    seekable, so `"r+"` raises io.UnsupportedOperation — which subclasses
    OSError, so it would be caught below and silently look like "no terminal".
    """
    try:
        return open("/dev/tty", mode)
    except OSError:
        return None


def _frames(stream: TextIO) -> str:
    try:
        _FRAMES_UNICODE.encode(stream.encoding or "utf-8")
        return _FRAMES_UNICODE
    except (UnicodeEncodeError, LookupError):
        return _FRAMES_ASCII


class Activity:
    """Spin on the terminal until the work finishes, then erase the line.

    A keypress that shows nothing for several seconds is indistinguishable from
    a hang, which is the complaint this exists to answer. The line is erased on
    exit so the answer lands on a clean row — including when the model fails,
    where the user must see the error and not a frozen spinner.
    """

    def __init__(self, label: str = "thinking", interval: float = 0.08) -> None:
        self.label = label
        self.interval = interval
        self._tty: Optional[TextIO] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._width = 0

    def __enter__(self) -> "Activity":
        self._tty = open_tty("w")
        if self._tty is None:
            return self
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> bool:
        self._stop.set()
        if self._thread is not None:
            # Bounded: a wedged terminal write must not outlive the command.
            self._thread.join(timeout=1.0)
        self._erase()
        if self._tty is not None:
            try:
                self._tty.close()
            except OSError:
                pass
        return False  # never swallow the exception

    def _spin(self) -> None:
        tty = self._tty
        assert tty is not None
        frames = _frames(tty)
        i = 0
        while not self._stop.is_set():
            text = f"{frames[i % len(frames)]} {self.label}"
            try:
                tty.write("\r" + text)
                tty.flush()
            except (OSError, ValueError):
                return  # terminal went away mid-spin; nothing to report
            self._width = max(self._width, len(text))
            i += 1
            self._stop.wait(self.interval)

    def _erase(self) -> None:
        if self._tty is None or not self._width:
            return
        try:
            self._tty.write("\r" + " " * self._width + "\r")
            self._tty.flush()
        except (OSError, ValueError):
            pass


def _width() -> int:
    return max(8, min(shutil.get_terminal_size((80, 24)).columns, MAX_RULE))


def rule(char: str = "#") -> str:
    return char * _width()


def open_rule(title: str, char: str = "#") -> str:
    """A rule with the command in it, so a scrollback full of output stays readable.

    `#` rather than `*`: if any of this is ever copied back to a prompt it is a
    comment, whereas `*` is a glob.
    """
    lead = f"{char * 4} {title} "
    pad = _width() - len(lead)
    return lead + char * pad if pad > 0 else lead.rstrip()
