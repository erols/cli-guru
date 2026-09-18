"""Configuration: defaults, file, environment. Stdlib only."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    # Measured on a CPU-only host, each model alone (bench/eval_ask.py and
    # bench/eval_hard.py; 5+ repeats per case, hard set run twice):
    #   model               easy  hard   median  resident
    #   qwen2.5-coder:1.5b   92%   64%    202ms    2.12G
    #   qwen2.5-coder:3b     83%   46%    489ms    3.37G
    #   qwen2.5-coder:7b     92%   79%    702ms    6.92G
    #   nemotron-3-nano:4b   80%    -     911ms    3.78G
    # 1.5b beats 3b on BOTH sets while being smaller and 2x faster, so 3b has
    # no niche. Default to 1.5b; 7b is the accuracy option for harder requests.
    "model": "qwen2.5-coder:1.5b",
    "host": "http://localhost:11434",
    "think": False,          # ask: measured 7x slower, no accuracy gain
    # explain: thinking generated 383 extra tokens -> 14.9s vs 3.7s, and the
    # non-thinking answer was already correct. The man page does the grounding.
    "think_explain": False,
    # Ollama unloads an idle model after 5 minutes by default, so the first
    # keypress after a break pays the cold-load penalty. Keeping it resident is
    # the difference between a snappy key and a visible stall.
    # "30m", "8h", or -1 to pin it in RAM until ollama restarts.
    "keep_alive": "8h",
    "timeout": 20,           # ask: a keypress must not hang the prompt
    "timeout_explain": 45,   # explain: a man page is a much larger prompt
    "history_lines": 10,
    "max_files": 50,
    # Listing available tools MEASURABLY hurts small models: qwen2.5-coder:3b
    # went from 25% to 75% on a four-case probe when the list was removed. It
    # sees `rg` and forces it into every answer with invented flags. Off by
    # default; enable only if your model is shown to benefit.
    "include_tools": False,
    # 12000 chars was ~3100 prompt tokens on a 4B model. 6000 keeps explain
    # responsive while still carrying the whole OPTIONS section for most tools.
    "max_man_chars": 6000,
    # When no man page exists, fall back to running `<cmd> --help`. OFF by
    # default: explain is what you reach for BEFORE running something, so it
    # must not run it for you. Opt in only if you trust what you paste.
    "explain_run_help": False,
}

_BOOL = {"true": True, "false": False, "yes": True, "no": False, "1": True, "0": False}


def config_dir() -> Path:
    """Per-platform config location. Ten lines, so no platformdirs dependency."""
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "cli-guru"
        return Path.home() / "AppData" / "Roaming" / "cli-guru"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "cli-guru"
    return Path.home() / ".config" / "cli-guru"


def _parse_simple_toml(text: str) -> Dict[str, Any]:
    """Flat key = value subset of TOML.

    Used only when tomllib is unavailable (Python < 3.11). The config is flat
    scalars by design, so this is sufficient and keeps us stdlib-only on 3.9/3.10.
    """
    out: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if val[:1] in ('"', "'"):
            # Take what is between the quotes and drop anything after them, so a
            # trailing comment does not end up inside the value. Splitting on "#"
            # first instead would corrupt a value that legitimately contains one
            # (a URL fragment, a colour). Both forms appear in the documented
            # config, and getting this wrong yields a model name like
            # `"qwen2.5-coder:1.5b"  # beats :3b`, which ollama then 404s on.
            quote = val[0]
            closing = val.find(quote, 1)
            if closing != -1:
                out[key] = val[1:closing]
                continue
            val = val[1:]  # unterminated quote — treat the remainder as bare
        else:
            val = val.split("#", 1)[0].strip()
        if val.lower() in _BOOL:
            out[key] = _BOOL[val.lower()]
        elif re.fullmatch(r"-?\d+", val):
            out[key] = int(val)
        elif val:
            out[key] = val
    return out


def _load_file(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_bytes()
    except (OSError, ValueError):
        return {}
    try:
        import tomllib  # Python 3.11+
        return dict(tomllib.loads(raw.decode("utf-8")))
    except ImportError:
        return _parse_simple_toml(raw.decode("utf-8", "replace"))
    except Exception:
        return {}


def _coerce(key: str, value: str) -> Any:
    default = DEFAULTS.get(key)
    if isinstance(default, bool):
        return _BOOL.get(str(value).lower(), default)
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    return value


def load(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Precedence: CLI flag > env > config file > default."""
    cfg = dict(DEFAULTS)
    cfg.update(_load_file(config_dir() / "config.toml"))

    env_map = {
        "model": "CLI_GURU_MODEL",
        "host": "OLLAMA_HOST",
        "timeout": "CLI_GURU_TIMEOUT",
        "think": "CLI_GURU_THINK",
    }
    for key, env in env_map.items():
        val = os.environ.get(env)
        if val:
            cfg[key] = _coerce(key, val)

    for key, val in (overrides or {}).items():
        if val is not None:
            cfg[key] = val

    cfg["host"] = normalise_host(str(cfg["host"]))
    return cfg


def normalise_host(host: str) -> str:
    """Accept `1.2.3.4:11434` as well as a full URL — OLLAMA_HOST is used both ways."""
    host = host.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    if not re.search(r":\d+$", host):
        host += ":11434"
    return host
