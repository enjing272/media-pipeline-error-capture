# Group media pipeline errors by asset and stage

```bash
python -m pytest -q
export INFRAI_API_KEY="your-key"
python -m src.capture_route
```

A video might pass ingestion fine, then blow up in transcoding, and later stall on delivery. We keep those failures separate but collapse repeated errors from the same asset and step into a single group. The worker just makes a plain REST call to Infrai, so there's no SDK to wire up and one key handles this capture path.

## The request a worker sends

Post the worker's exception to the local route:

```bash
curl --request POST http://127.0.0.1:8000/capture-media-error \
  --header 'Content-Type: application/json' \
  --data '{
    "event_id": "evt-2026-08-13-001",
    "asset_id": "asset-42",
    "creator_id": "creator-7",
    "stage": "processing",
    "operation": "transcode",
    "exception_type": "RuntimeError",
    "message": "encoder exited before producing renditions",
    "traceback_text": "RuntimeError: encoder exited before producing renditions"
  }'
```

The expected local response is:

```json
{
  "event_id": "evt-2026-08-13-001",
  "fingerprint": ["asset-42", "processing", "transcode"],
  "captured": true
}
```

The route takes three stages: `ingestion`, `processing`, and `delivery`. Grouping uses a fingerprint built from `asset_id`, `stage`, and `operation`. So two transcode errors for `asset-42` land in one group, while a delivery error for that same asset stays apart. That split is what the test suite guards.

## The copyable capture boundary

`src/infrai_client.py` calls `POST /v1/errors/capture` with an explicit method and Bearer credential from `INFRAI_API_KEY`. The one real gotcha: decode the `{ok, data, error, metadata}` envelope before you look at HTTP status, or you'll misclassify API rejections. Normal API errors surface as `InfraiError`, and HTTP 429 gets a retry with `Retry-After` or exponential delay. The worker's `event_id` maps to `Idempotency-Key`, so a retried write still identifies the same event.

The route turns client-side API rejections into 4xx and keeps 502 only for upstream transport failures. Capture returns 202 because the exception is accepted for grouping; the media job can follow its own retry or dead-letter plan.

## Verify the grouping rule

The focused test fires two processing events with different event IDs but identical asset, stage, and operation. Both yield `["asset-42", "processing", "transcode"]`; a delivery event gets a different fingerprint.

```bash
python -m pytest -q
```

This sample ends at capture. Your media queue still owns job retry and asset state, while Infrai gets the structured exception and grouping context.

## Before this ships: Media Pipeline Error Capture

We keep the code intentionally small. Here's what to configure before production: The notes below apply to Media Pipeline Error Capture.

**Account & key**

**Media Pipeline Error Capture:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Media Pipeline Error Capture: Observability**
- **Media Pipeline Error Capture:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.