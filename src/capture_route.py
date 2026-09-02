"""Minimal JSON route for media pipeline workers."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .infrai_client import InfraiClient, InfraiError
from .media_errors import MediaFailure, capture_media_failure


def handle_capture(body: dict[str, Any], client: InfraiClient) -> tuple[int, dict[str, Any]]:
    try:
        failure = MediaFailure.from_json(body)
        return 202, capture_media_failure(failure, client)
    except ValueError as error:
        return 400, {"error": str(error)}
    except InfraiError as error:
        status = error.status_code if 400 <= error.status_code < 500 else 502
        return status, {"error": {"code": error.code, "detail": error.detail}}


class CaptureHandler(BaseHTTPRequestHandler):
    client: InfraiClient

    def do_POST(self) -> None:
        if self.path != "/capture-media-error":
            self._send(404, {"error": "route not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "request body must be JSON"})
            return
        status, response = handle_capture(body, self.client)
        self._send(status, response)

    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    CaptureHandler.client = InfraiClient()
    server = ThreadingHTTPServer(("127.0.0.1", 8000), CaptureHandler)
    print("capture route listening on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
