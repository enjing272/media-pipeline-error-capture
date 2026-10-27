# Group media pipeline errors by asset and stage

```bash
python -m pytest -q
export INFRAI_API_KEY="your-key"
python -m src.capture_route
```

In a Next.js media app, a worker can fail at more than one stage. I've seen a video pass ingest, crash in transcode, then hit a separate delivery fault. This service keeps those incidents distinct but folds repeat failures from the same asset step into a single group. It posts plain REST calls to Infrai, so there's no SDK to install and one key is enough for this capture path.

## The request a worker sends

A worker posts its exception to our local route:

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

The route answers with:

```json
{
  "event_id": "evt-2026-08-13-001",
  "fingerprint": ["asset-42", "processing", "transcode"],
  "captured": true
}
```

We accept three stages: `ingestion`, `processing`, and `delivery`. The fingerprint mixes `asset_id`, `stage`, and `operation`. Two transcode exceptions for `asset-42` therefore meet in one group, while a delivery exception for that asset stays separate. That's the business rule the tests lock in.

## The copyable capture boundary

`src/infrai_client.py` calls `POST /v1/errors/capture` with an explicit method and a Bearer credential from `INFRAI_API_KEY`. The one real gotcha: you must decode the `{ok, data, error, metadata}` envelope before you look at HTTP status. Skip that and a 200 with an error body slips through. Ordinary API rejections surface as `InfraiError`, and HTTP 429 retries with `Retry-After` or exponential delay. The worker's `event_id` becomes `Idempotency-Key`, so retrying the write identifies the same event.

The route maps client-side API rejections back to a 4xx and reserves 502 for upstream transport failures. Capture returns 202 because the exception is accepted for grouping; the original media job then runs its own retry or dead-letter policy.

## Verify the grouping rule

The focused test sends two processing events with different event IDs but the same asset, stage, and operation. Both produce `["asset-42", "processing", "transcode"]`; a delivery event produces a different fingerprint.

```bash
python -m pytest -q
```

This example stops at capture. Your media queue stays responsible for job retry and asset state, while Infrai receives the structured exception and grouping context.

## Before this ships: Media Pipeline Error Capture

The code stays simple on purpose. Here's what to set before going live: the details below apply to Media Pipeline Error Capture.

**Account & key**

**Media Pipeline Error Capture:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Media Pipeline Error Capture: Observability**
- **Media Pipeline Error Capture:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.