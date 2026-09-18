"""Backend tests run against a stub HTTP server on an ephemeral port.

No real ollama is contacted, so the suite passes on a machine that has never
installed it.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from cli_guru import backend
from cli_guru.backend import BackendError, OllamaBackend


class _Handler(BaseHTTPRequestHandler):
    reply = {"message": {"role": "assistant", "content": "ls -la", "thinking": "reasoning here"}}
    status = 200

    def _send(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.received = json.loads(self.rfile.read(length))
        type(self).last_request = self.received
        self._send(type(self).reply, type(self).status)

    def do_GET(self):
        self._send({"models": [{"name": "test-model:1b"}]})

    def log_message(self, *args):
        pass


class BackendTestCase(unittest.TestCase):
    def setUp(self):
        _Handler.reply = {
            "message": {"content": "ls -la", "thinking": "reasoning here"}
        }
        _Handler.status = 200
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_returns_content_and_thinking_separately(self):
        content, thinking = OllamaBackend(self.host, "test-model:1b").chat("sys", "user")
        self.assertEqual(content, "ls -la")
        self.assertEqual(thinking, "reasoning here")

    def test_thinking_is_never_mixed_into_content(self):
        """Concatenating them would paste model reasoning into a live prompt."""
        content, _ = OllamaBackend(self.host, "test-model:1b").chat("sys", "user")
        self.assertNotIn("reasoning", content)

    def test_think_flag_and_options_sent(self):
        OllamaBackend(self.host, "test-model:1b").chat(
            "sys", "user", think=False, num_predict=160
        )
        req = _Handler.last_request
        self.assertIs(req["think"], False)
        self.assertEqual(req["options"]["num_predict"], 160)
        self.assertIn("repeat_penalty", req["options"])
        self.assertEqual(req["messages"][0]["role"], "system")

    def test_missing_content_yields_empty_string(self):
        _Handler.reply = {"message": {}}
        content, _ = OllamaBackend(self.host, "test-model:1b").chat("sys", "user")
        self.assertEqual(content, "")

    def test_check_passes_for_present_model(self):
        self.assertIn("ok", OllamaBackend(self.host, "test-model:1b").check())

    def test_check_names_missing_model_and_how_to_pull(self):
        with self.assertRaises(BackendError) as ctx:
            OllamaBackend(self.host, "absent:9b").check()
        self.assertIn("ollama pull absent:9b", str(ctx.exception))

    def test_unreachable_host_message_is_actionable(self):
        backend = OllamaBackend("http://127.0.0.1:1", "test-model:1b", timeout=2)
        with self.assertRaises(BackendError) as ctx:
            backend.chat("sys", "user")
        message = str(ctx.exception)
        self.assertIn("no ollama at", message)
        self.assertIn("ollama serve", message)

    def test_http_error_surfaces_as_backend_error(self):
        _Handler.status = 500
        with self.assertRaises(BackendError):
            OllamaBackend(self.host, "test-model:1b").chat("sys", "user")


class ResponseSizeTestCase(unittest.TestCase):
    """$OLLAMA_HOST may point anywhere, over plain HTTP. A reply that never ends
    must not be read until the process runs out of memory."""

    class _Endless:
        def read(self, n=-1):
            return b"x" * n if n and n > 0 else b"x" * (backend.MAX_RESPONSE_BYTES * 2)

    class _Normal:
        def read(self, n=-1):
            return b'{"ok": 1}'

    def test_oversized_response_is_refused(self):
        with self.assertRaises(BackendError) as ctx:
            backend._read_capped(self._Endless())
        self.assertIn("refusing", str(ctx.exception))

    def test_normal_response_passes_through(self):
        self.assertEqual(backend._read_capped(self._Normal()), b'{"ok": 1}')


if __name__ == "__main__":
    unittest.main()
