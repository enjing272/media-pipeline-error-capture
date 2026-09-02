"""Domain model and grouping policy for a streaming media pipeline."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Literal

from .infrai_client import InfraiClient

PipelineStage = Literal["ingestion", "processing", "delivery"]


@dataclass(frozen=True)
class MediaFailure:
    event_id: str
    asset_id: str
    creator_id: str
    stage: PipelineStage
    operation: str
    exception_type: str
    message: str
    traceback_text: str

    @classmethod
    def from_json(cls, body: dict[str, Any]) -> "MediaFailure":
        required = (
            "event_id",
            "asset_id",
            "creator_id",
            "stage",
            "operation",
            "exception_type",
            "message",
            "traceback_text",
        )
        missing = [name for name in required if not isinstance(body.get(name), str) or not body[name]]
        if missing:
            raise ValueError(f"missing string fields: {', '.join(missing)}")
        if body["stage"] not in ("ingestion", "processing", "delivery"):
            raise ValueError("stage must be ingestion, processing, or delivery")
        return cls(**{name: body[name] for name in required})

    def capture_payload(self) -> dict[str, Any]:
        return {
            "title": f"{self.stage}/{self.operation} failed",
            "message": f"{self.exception_type}: {self.message}",
            "level": "error",
            "fingerprint": [self.asset_id, self.stage, self.operation],
            "exception": self.traceback_text,
            "context": {
                "event_id": self.event_id,
                "asset_id": self.asset_id,
                "creator_id": self.creator_id,
                "stage": self.stage,
                "operation": self.operation,
            },
        }


def capture_media_failure(failure: MediaFailure, client: InfraiClient) -> dict[str, Any]:
    """Capture one failure and return the concrete grouping decision."""
    client.capture(failure.capture_payload(), failure.event_id)
    return {
        "event_id": failure.event_id,
        "fingerprint": failure.capture_payload()["fingerprint"],
        "captured": True,
    }


def capture_exception(
    *,
    event_id: str,
    asset_id: str,
    creator_id: str,
    stage: PipelineStage,
    operation: str,
    error: Exception,
    client: InfraiClient,
) -> dict[str, Any]:
    failure = MediaFailure(
        event_id=event_id,
        asset_id=asset_id,
        creator_id=creator_id,
        stage=stage,
        operation=operation,
        exception_type=type(error).__name__,
        message=str(error),
        traceback_text="".join(traceback.format_exception(error)),
    )
    return capture_media_failure(failure, client)
