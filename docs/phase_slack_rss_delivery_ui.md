# Phase plan: Slack / outbound webhooks, RSS ingress, delivery UI

End goal: **RSS or other external signal → public `POST /webhooks/news` → full pipeline → PDF + optional email + Slack (or generic webhook) summary**, with a **visible delivery line** on the dashboard.

This document is ordered for **fast demo value**: ship backend delivery first, then ops (tunnel + Make), then UI.

---

## Current baseline (do not redo)

| Piece | Location | Notes |
|-------|----------|--------|
| Webhook ingress | `backend/api/webhooks.py` → `dispatch_pipeline` | Already runs E2E on `POST /webhooks/news` |
| Email delivery | `backend/services/delivery.py` → `deliver_report()` | SendGrid; publishes `delivery.completed` |
| Completion + PDF | `backend/services/background.py` → `_complete_workflow` | Merges `delivery` into `workflow.completed` payload |
| Real-time UI | `frontend/js/websocket.js` + `activity.js` | Subscribes to Redis-backed `/ws/activity` |
| Config stub | `backend/config.py` | `SLACK_WEBHOOK_URL` exists but **is not used in code** |

---

## Phase 1 — Backend: outbound Slack + generic webhook (+ logging)

**Objective:** One delivery module posts to **Slack Incoming Webhook** and/or an **optional second URL** (Teams, Discord, Zapier catch hook — same JSON or adapter pattern).

### 1.1 Configuration (`backend/config.py` + `.env.example`)

- Keep `SLACK_WEBHOOK_URL` (Slack Incoming Webhook URL).
- Add optional **`OUTBOUND_WEBHOOK_URL`** — generic HTTPS endpoint for a short JSON payload (non-Slack consumers).
- Optional flags: `DELIVERY_SLACK_ENABLED=true`, `DELIVERY_SENDGRID_ENABLED=true` (default: infer from non-empty keys to avoid silent double-send surprises).

### 1.2 Implement `deliver_report` extensions (`backend/services/delivery.py`)

Suggested shape:

1. **After** a successful report (same entry point as today), run in order:
   - Existing **SendGrid** block (unchanged behavior when configured).
   - **Slack**: `POST` to `SLACK_WEBHOOK_URL` with [Slack incoming webhook JSON](https://api.slack.com/messaging/webhooks): `{"text": "...", "blocks": [...]}`.
     - Include: report title, competitor, confidence, truncated exec brief (e.g. first ~800 chars), `workflow_id`, and a note that full PDF is on disk / API (`GET /api/reports`).
   - **Generic webhook**: `POST` JSON to `OUTBOUND_WEBHOOK_URL` with `{ "event": "report.completed", "workflow_id", "competitor", "title", "confidence", "exec_preview", "pdf_filename" }`.
2. **Never** fail the pipeline: wrap each outbound call in try/except; log and continue.
3. **Return value**: extend the dict returned by `deliver_report` to a **list or map of channels**, e.g.  
   `channels: [{ "channel": "sendgrid", "success": bool, ... }, { "channel": "slack", ... }]`.

### 1.3 Events (`publish_event`)

- Emit **`delivery.completed`** once per logical completion with:
  - `workflow_id`
  - `channels`: array of `{ channel, success, message | error }`
  - `demo_mode` if nothing configured
- Keep backward compatibility: existing consumers that expect single `channel` can read `channels[0]` or a `summary` string.

### 1.4 Persistence (optional but recommended)

- In `_complete_workflow` (`background.py`), merge delivery summary into `workflow.extra_data["delivery"]` (already partly there via `completion_payload["delivery"]` — ensure **full** multi-channel result is stored).

**Exit criteria:** With `SLACK_WEBHOOK_URL` set, a completed run shows a message in Slack; logs show `slack_delivery_sent` or clear failure reason.

---

## Phase 2 — Completion logging & observability

**Objective:** Operators can see **what was delivered** without opening Slack.

### 2.1 Structured logging

- Log one line per channel outcome: `delivery_channel_result`, `workflow_id`, `channel`, `success`, `http_status` (if applicable).

### 2.2 WebSocket / activity feed

- Ensure `delivery.completed` and/or enriched `workflow.completed` payload is **subscribed** on the WebSocket path (same Redis pub/sub path as today — verify `publish_event` fan-out).

**Exit criteria:** Grep logs or activity JSON shows multi-channel delivery for one workflow.

---

## Phase 3 — Ops: tunnel + Make.com RSS → `/webhooks/news`

**Objective:** “News arrives” without manual `curl`.

### 3.1 Public HTTPS URL to your API

- Run backend reachable at `https://<host>/webhooks/news` (deployed VM, fly.io, Railway, etc.) **or** dev tunnel:
  - **ngrok**: `ngrok http 8000` → copy `https://....ngrok-free.app`
  - **Cloudflare Tunnel** (stable URL): point to `localhost:8000`

### 3.2 Make.com (or Zapier) scenario

1. **Trigger:** RSS module — feed URL of your choice (tech news, competitor blog).
2. **Router / filter (recommended):** Keyword or competitor name contains X — avoids cost on every headline.
3. **HTTP → Make a request:** `POST` `{tunnel}/webhooks/news`
   - **Headers:** `Content-Type: application/json`
   - **Body** must match `SignalInput` in `backend/models/schemas.py`:
     - **`title`** (required): e.g. RSS item title
     - **`source`:** e.g. `"rss"`
     - **`url`:** item link
     - **`content`:** summary or full description (optional)
     - **`competitor_name`:** your tracked name (strongly recommended for consistent profile + Sentinel context)
     - **`custom_question`:** e.g. *“What is the competitive impact of this announcement?”*

4. Run once **manually** in Make; confirm `202` from ASCENT and a new row in `webhook_events`.

### 3.3 Safety rails (should-ship, same phase if time)

- Rate limit or dedupe in Make (same `title`+`url` within 1 hour).
- Use a **dedicated** Make scenario for demo RSS so you don’t spam production Slack.

**Exit criteria:** New RSS item → Make POST → ASCENT logs pipeline start → Slack message when done (Phase 1 on).

---

## Phase 4 — Frontend: delivery status line

**Objective:** User sees **email / Slack / skipped** without opening network tab.

### 4.1 Event handling (`frontend/js/websocket.js` or `activity.js`)

- On message where `event_type === 'delivery.completed'` **or** `workflow.completed` includes `delivery`:
  - Render a compact **success / warning / error** line in the activity feed (reuse styles similar to verifier banner but neutral/blue for success).
  - Text examples:
    - “Delivery: Slack ✓ · SendGrid skipped (not configured)”
    - “Delivery: Slack ✗ HTTP 400 — check webhook URL”

### 4.2 Optional: sticky “Last delivery” card

- Small card near **Manual Trigger** showing last `workflow_id` + channels from most recent `workflow.completed` (requires either client state from WS only, or lightweight `GET /api/health/stats` extension later).

**Exit criteria:** Completing a run shows a one-line delivery summary in the dashboard activity stream.

---

## Phase 5 — QA checklist (run in order)

| Step | Action | Pass |
|------|--------|------|
| 1 | Unit/integration: mock `httpx` POST to Slack URL | No crash; `delivery.completed` has `channels` |
| 2 | Local: finish `golden_path.py` or manual analyze with Slack URL in `.env` | Slack channel receives message |
| 3 | Unset Slack URL | UI/logs show “skipped” / demo mode, pipeline still completes |
| 4 | Make.com fires test POST to tunnel | Workflow row + report + Slack |
| 5 | Browser: open `index2.html` | Delivery line appears on completion |

---

## Phase 6 — Optional polish (after the above)

- **Discord** / **Teams**: second Incoming Webhook URL or reuse `OUTBOUND_WEBHOOK_URL` with provider-specific payload builders in `delivery.py`.
- **Link in Slack message**: if you deploy a public **report viewer URL**, add `FRONTEND_URL/reports?id=…` (needs report ID in payload from `background.py`).
- **README**: replace references to non-existent `notifications.py` with `delivery.py` + env vars.

---

## Suggested ownership & timebox

| Phase | Owner | Rough time |
|-------|--------|------------|
| 1 Backend | 2–4 h |
| 2 Logging | 0.5 h |
| 3 Make + tunnel | 1–2 h (mostly ops) |
| 4 UI | 1–2 h |
| 5 QA | 1 h |

---

## Risk notes

- **Slack rate limits:** rare for hackathon volume; retry once on 429.
- **Message size:** Slack `text`/`blocks` limits — keep exec preview short; link to PDF/API for full content.
- **Secrets:** never commit real webhook URLs; use `.env` and CI secrets.
