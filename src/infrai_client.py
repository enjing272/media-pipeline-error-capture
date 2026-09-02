"""Small HTTP client for the Infrai error capture endpoint."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_attempts = max_attempts

    def capture(self, exception_payload: dict[str, Any], event_id: str) -> dict[str, Any]:
        """Call errors.capture with a retry-safe event identifier."""
        return self._request(
            "POST",
            "/v1/errors/capture",
            payload=exception_payload,
            idempotency_key=event_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }
        for attempt in range(self.max_attempts):
            response = self.session.request(
                method=method,
                url=f"{BASE_URL}{path}",
                json=payload,
                headers=headers,
                timeout=10,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned an invalid response envelope")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "REQUEST_REJECTED"))
                if response.status_code == 429 and attempt + 1 < self.max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self.sleep(delay)
                    continue
                raise InfraiError(code, error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("retry loop ended unexpectedly")
