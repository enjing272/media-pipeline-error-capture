from typing import Any

from src.capture_route import handle_capture
from src.media_errors import MediaFailure


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str]] = []

    def capture(self, payload: dict[str, Any], event_id: str) -> dict[str, Any]:
        self.calls.append((payload, event_id))
        return {"event_id": event_id}


def failure(stage: str, operation: str) -> dict[str, str]:
    return {
        "event_id": f"evt-{stage}",
        "asset_id": "asset-42",
        "creator_id": "creator-7",
        "stage": stage,
        "operation": operation,
        "exception_type": "RuntimeError",
        "message": "media step failed",
        "traceback_text": "RuntimeError: media step failed",
    }


def test_route_groups_repeated_processing_errors_by_asset_stage_and_operation() -> None:
    client = RecordingClient()

    first_status, first = handle_capture(failure("processing", "transcode"), client)  # type: ignore[arg-type]
    second_body = failure("processing", "transcode")
    second_body["event_id"] = "evt-processing-retry"
    second_status, second = handle_capture(second_body, client)  # type: ignore[arg-type]

    assert (first_status, second_status) == (202, 202)
    assert first["fingerprint"] == second["fingerprint"] == ["asset-42", "processing", "transcode"]
    assert client.calls[0][1] != client.calls[1][1]


def test_delivery_and_processing_failures_do_not_share_a_group() -> None:
    processing = MediaFailure.from_json(failure("processing", "package"))
    delivery = MediaFailure.from_json(failure("delivery", "package"))

    assert processing.capture_payload()["fingerprint"] != delivery.capture_payload()["fingerprint"]


def test_route_rejects_an_unknown_pipeline_stage() -> None:
    status, body = handle_capture(failure("archive", "store"), RecordingClient())  # type: ignore[arg-type]

    assert status == 400
    assert body == {"error": "stage must be ingestion, processing, or delivery"}
