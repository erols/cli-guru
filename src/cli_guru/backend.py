"""Model I/O. The ONLY module that talks to a model.

Everything else (context, man parsing, sanitising, shell adapters) must not
import this or know it exists — see CLAUDE.md "The seam that keeps this
reversible". Swapping in another provider means writing one more class here.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional, Tuple


class BackendError(Exception):
    """User-facing failure. The message is printed verbatim to stderr."""


# A real reply is a few KB: ask is capped at 160 predicted tokens, explain at
# 700. This bound exists for the case where the host is not what we think it is
# — `$OLLAMA_HOST` may point across a LAN, over plain HTTP — so a hostile or
# broken endpoint cannot stream until the process runs out of memory.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _tagged(name: str) -> str:
    """Resolve a reference the way ollama does: no tag means `:latest`.

    Only the final path segment is inspected, so the port in a registry host
    (`localhost:5000/my-model`) is not mistaken for a tag.
    """
    return name if ":" in name.rsplit("/", 1)[-1] else f"{name}:latest"


def _pulled(model: str, names: list) -> bool:
    """Is `model` among the pulled tags?

    `check` used to compare the raw strings, so a configured `qwen2.5-coder`
    was reported as not pulled even with `qwen2.5-coder:latest` present — while
    `ask` worked fine, because ollama resolves the tag itself. A diagnostic
    that contradicts the thing it diagnoses is worse than no diagnostic.
    """
    return _tagged(model) in {_tagged(n) for n in names if n}


def _read_capped(resp) -> bytes:
    data = resp.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise BackendError(
            f"ollama sent more than {MAX_RESPONSE_BYTES // (1024 * 1024)}MB — refusing it"
        )
    return data


class OllamaBackend:
    def __init__(
        self, host: str, model: str, timeout: int = 20, keep_alive: str = "8h"
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.keep_alive = keep_alive

    def chat(
        self, system: str, user: str, *, think: bool = False, num_predict: int = 160
    ) -> Tuple[str, Optional[str]]:
        """Return (content, thinking). `thinking` is for --debug only, never output.

        `num_predict` is deliberately tight for ask: this model can degenerate
        into a repetition loop (observed: `--quiet --quiet --quiet ...` for 20s
        until the token cap). A low cap bounds the damage; repeat_penalty makes
        it rarer.
        """
        payload = {
            "model": self.model,
            "stream": False,
            "think": think,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Keeps the model resident so the next keypress is warm.
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.1,
                "num_predict": num_predict,
                "repeat_penalty": 1.15,
            },
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(_read_capped(resp).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(_read_capped(exc).decode("utf-8")).get("error", "")
            except Exception:
                pass
            if exc.code == 404 or "not found" in detail.lower():
                raise BackendError(
                    f"model {self.model!r} not found (pull it with: ollama pull {self.model})"
                ) from exc
            raise BackendError(f"ollama returned HTTP {exc.code}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise BackendError(
                    f"timed out after {self.timeout}s — try a smaller model or raise timeout"
                ) from exc
            raise BackendError(
                f"no ollama at {self.host} (start it with: ollama serve, "
                f"or set OLLAMA_HOST)"
            ) from exc
        except TimeoutError as exc:
            raise BackendError(f"timed out after {self.timeout}s — try a smaller model") from exc
        except json.JSONDecodeError as exc:
            raise BackendError("ollama returned a malformed response") from exc

        msg = body.get("message") or {}
        # Thinking models return `thinking` alongside `content`. Read content ONLY:
        # concatenating them would paste the model's reasoning into a live prompt.
        return msg.get("content") or "", msg.get("thinking")

    def check(self) -> str:
        """Verify reachability and that the model is pulled. Returns a status line."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=self.timeout) as resp:
                tags = json.loads(_read_capped(resp).decode("utf-8"))
        except urllib.error.URLError as exc:
            raise BackendError(
                f"no ollama at {self.host} (start it with: ollama serve, or set OLLAMA_HOST)"
            ) from exc
        names = [m.get("name", "") for m in tags.get("models", [])]
        if not _pulled(self.model, names):
            available = ", ".join(names) or "none"
            raise BackendError(
                f"model {self.model!r} not pulled (available: {available}; "
                f"get it with: ollama pull {self.model})"
            )
        return f"ok: {self.host} reachable, model {self.model} present"
