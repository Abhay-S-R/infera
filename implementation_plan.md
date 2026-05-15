# ASCENT — Implementation Plan

**Autonomous Strategic Competitive Event & News Tracker**

> A multi-agent pipeline that monitors competitive signals, autonomously researches and analyzes them, and delivers structured intelligence reports — with zero human intervention after the trigger.

---

## Team Roles

| Member | Role | Primary Responsibility |
|--------|------|----------------------|
| **Dev 1** | Infrastructure Lead | FastAPI, database, Docker, webhooks, API routes, background tasks |
| **Dev 2** | Agent Lead | LangGraph pipeline, Sentinel + Scout agents, tool integrations |
| **Dev 3** | Frontend Lead | Dashboard UI, WebSocket real-time feed, visualizations, UX polish |
| **Dev 4** | Integration Lead | Strategist + Scribe agents, Omium tracing, testing, demo prep, writeup |

---

## Complete Feature List

### A. Event Ingress (Webhook-Driven Triggers)

| # | Feature | Description | Eval Axis |
|---|---------|-------------|-----------|
| A1 | **News Webhook Endpoint** | `POST /webhooks/news` — receives payloads from news APIs/RSS feeds, stores immediately in DB, triggers pipeline | Tooling (15%) |
| A2 | **Scheduled Scan Trigger** | `POST /webhooks/scheduled` — cron-triggered (APScheduler) periodic competitive scan for tracked competitors | Autonomy (25%) |
| A3 | **Manual Analysis Request** | `POST /api/analyze` — user submits a specific question via dashboard ("What is Competitor X doing in market Y?") | UX / Usefulness (20%) |
| A4 | **Webhook Payload Logging** | Every incoming webhook stored in DB with timestamp, source, raw payload — full audit trail | Architecture (10%) |

### B. Multi-Agent Pipeline (5 Agents)

| # | Agent | Role | Tools Used | Eval Axis |
|---|-------|------|-----------|-----------|
| B1 | **Sentinel** (Monitor) | Filters incoming signals, scores relevance, decides what's worth investigating | LLM reasoning, DB query (historical signals) | Multi-Agent (20%) |
| B2 | **Scout** (Research) | Deep web search, gathers evidence from multiple sources, structures raw findings | Tavily web search, News APIs, URL scraping | Tooling (15%) |
| B3 | **Strategist** (Analysis) | Synthesizes research into competitive analysis: impact assessment, market positioning, strategic implications | LLM deep reasoning, code execution (data analysis) | Deep Reasoning |
| B4 | **Arbiter** (Validator) | Fact-checks Strategist's claims against Scout's evidence, scores confidence, can trigger re-research | LLM reasoning, source cross-referencing | Autonomy (25%) |
| B5 | **Scribe** (Report) | Generates the final deliverable: structured report with executive summary, detailed analysis, sources, confidence scores | Markdown generation, PDF creation, notification dispatch | Usefulness (20%) |

### C. Autonomous Execution Features

| # | Feature | Description | Eval Axis |
|---|---------|-------------|-----------|
| C1 | **Quality Gates** | Between each agent, a confidence check determines if work is sufficient or needs re-doing | Autonomy (25%) |
| C2 | **Semantic Retry Loops** | When the Arbiter rejects analysis, Scout retries with *modified search terms*, not the same query | Autonomy (25%) |
| C3 | **Token Budget System** | Hard caps on per-agent and per-workflow token usage, prevents cost explosion | Architecture (10%) |
| C4 | **Tiered Context Management** | Essential → Summarized → RAG-retrievable context passing between agents | Multi-Agent (20%) |
| C5 | **Crash Recovery** | LangGraph + PostgreSQL checkpointing — resume from last successful agent on crash | Autonomy (25%) |
| C6 | **Graceful Degradation** | If an external API fails, system uses cached results or flags for manual review instead of crashing | Autonomy (25%) |

### D. Dashboard (Frontend)

| # | Feature | Description | Eval Axis |
|---|---------|-------------|-----------|
| D1 | **Live Agent Activity Feed** | WebSocket-powered real-time feed showing what each agent is doing right now | Demo (10%) |
| D2 | **Pipeline Visualization** | Visual flow showing Sentinel → Scout → Strategist → Arbiter → Scribe with status indicators | Demo (10%) |
| D3 | **Report Archive** | Browse all completed analyses with search, filtering by date/competitor/confidence | Usefulness (20%) |
| D4 | **Report Detail View** | Full report display: executive summary, detailed analysis, sources, confidence scores, agent trace | Usefulness (20%) |
| D5 | **Manual Trigger Form** | Submit a custom competitive intelligence question from the dashboard | Usefulness (20%) |
| D6 | **Competitor Configuration** | Add/remove tracked competitors and industries for scheduled scans | Usefulness (20%) |
| D7 | **System Health Panel** | Show active workflows, recent completions, error rates, token usage | Architecture (10%) |

### E. Observability & Tracing

| # | Feature | Description | Eval Axis |
|---|---------|-------------|-----------|
| E1 | **Omium SDK Integration** | `@omium.trace` on every agent, auto-instrument LangGraph | Bonus (+10%) |
| E2 | **Causal Trace Linking** | Webhook → Sentinel → Scout → Strategist → Arbiter → Scribe linked in Omium dashboard | Bonus (+10%) |
| E3 | **Structured Logging** | Every agent step logged with input/output, duration, token count, errors | Architecture (10%) |
| E4 | **Cost Tracking** | Per-workflow and per-agent token usage and estimated cost displayed in dashboard | Architecture (10%) |

### F. Delivery & Output

| # | Feature | Description | Eval Axis |
|---|---------|-------------|-----------|
| F1 | **Markdown Reports** | Primary output: structured markdown with sections, tables, confidence indicators | Usefulness (20%) |
| F2 | **PDF Export** | Generate downloadable PDF from the report | Tooling (15%) |
| F3 | **Notification System** | Post summary to configured Slack webhook or email on report completion | Tooling (15%) |

---

## Tech Stack (Right-Sized for 24 Hours)

```
Backend:
  ├── Python 3.12
  ├── FastAPI (REST API + WebSocket + webhook endpoints)
  ├── LangGraph (agent orchestration + state graph)
  ├── Google Gemini 2.0 Flash (LLM — fast + cheap)
  ├── Tavily API (web search tool)
  ├── PostgreSQL (state persistence + report storage + checkpointing)
  ├── Redis (pub/sub for real-time WebSocket events)
  ├── APScheduler (scheduled scan trigger)
  ├── Omium SDK (tracing + observability)
  └── WeasyPrint or FPDF (PDF generation)

Frontend:
  ├── HTML + CSS + Vanilla JS  (fast to build, no framework overhead)
  ├── WebSocket client (real-time agent activity feed)
  └── Marked.js (render markdown reports in browser)

Infrastructure:
  ├── Docker Compose (PostgreSQL + Redis + Backend + Frontend — one command)
  └── ngrok (webhook ingress for demo)
```

> [!IMPORTANT]
> **Why not Next.js for the frontend?** In a 24-hour hackathon with 4 people, a static HTML/CSS/JS frontend with WebSocket is faster to build, easier to debug, and has zero build-step overhead. The frontend is a presentation layer — the product value is in the agent pipeline.

---

## Phase-by-Phase Execution Plan

### Phase 0 — Foundation (Hours 0–2)

**Goal:** Everyone can run the project locally. All services connected.

| Dev | Task | Deliverable |
|-----|------|-------------|
| **Dev 1** | Docker Compose: PostgreSQL + Redis. Database schema (webhooks, reports, workflows, competitors tables). FastAPI skeleton with health check. | `docker-compose up` works. DB migrations run. `GET /health` returns 200. |
| **Dev 2** | LangGraph project structure. Define `PipelineState` TypedDict. Create empty graph with all 5 nodes wired. Basic Gemini client wrapper. | `python -m ascent.pipeline` runs the empty graph without errors. |
| **Dev 3** | Frontend scaffold: `index.html`, `styles.css`, `app.js`. Dashboard layout with sidebar + main content area. WebSocket connection stub. | Open `index.html` in browser → see the dashboard skeleton. |
| **Dev 4** | Environment setup: `.env.example` with all API keys. README quickstart. Shared utility modules: logging, config, structured output schemas (Pydantic models for all agent outputs). | Every dev can `cp .env.example .env`, fill keys, and run. |

**Checkpoint:** `docker-compose up` starts all services. Everyone can access the DB. FastAPI serves at `localhost:8000`. Frontend loads at `localhost:3000`.

---

### Phase 1 — Core Agents (Hours 2–8)

**Goal:** The agent pipeline works end-to-end with real LLM calls and real web search.

| Dev | Task | Deliverable |
|-----|------|-------------|
| **Dev 1** | Webhook endpoints: `POST /webhooks/news`, `POST /webhooks/scheduled`, `POST /api/analyze`. Background task runner (FastAPI BackgroundTasks or Celery). API route: `GET /api/reports`, `GET /api/reports/{id}`, WebSocket `/ws/activity`. Redis pub/sub for activity events. | Webhooks receive payloads → store in DB → trigger pipeline in background. WebSocket streams events. |
| **Dev 2** | **Sentinel Agent:** Takes raw signal, uses LLM to score relevance (0-1), filters noise, extracts key entities (company, event type, market). **Scout Agent:** Uses Tavily to search the web (3-5 queries per signal), scrapes key URLs, structures findings into `ResearchOutput` schema. | Feed a news payload → Sentinel filters → Scout researches → structured research output stored. |
| **Dev 3** | Dashboard: real-time activity feed (WebSocket), pipeline visualization (5 nodes with status colors), manual trigger form, report list view, report detail view (render markdown). | Dashboard shows live agent activity. Can submit manual analysis. Reports display beautifully. |
| **Dev 4** | **Strategist Agent:** Takes `ResearchOutput`, produces competitive analysis with impact assessment, market implications, strategic recommendations. **Scribe Agent:** Takes validated analysis, generates structured markdown report with executive summary, detailed findings, source citations, confidence scores. | Research → Analysis → Report. Full text output generated. |

**Checkpoint:** Submit a webhook payload → watch Sentinel filter it → Scout researches → Strategist analyzes → Scribe generates report → report appears in dashboard.

> [!WARNING]
> **This is the most critical checkpoint.** If the end-to-end pipeline doesn't work by Hour 8, everything downstream is blocked. All 4 devs should drop their tasks and debug together if needed.

---

### Phase 2 — Autonomy & Reliability (Hours 8–12)

**Goal:** The system is genuinely autonomous: validates, retries, recovers, manages costs.

| Dev | Task | Deliverable |
|-----|------|-------------|
| **Dev 1** | LangGraph PostgreSQL checkpointer integration. Crash recovery testing (kill process mid-pipeline, restart, verify it resumes). Scheduled scan with APScheduler (every N minutes, scan tracked competitors). | Kill the process mid-analysis → restart → pipeline resumes from last agent. Scheduled scans fire automatically. |
| **Dev 2** | **Arbiter Agent:** Cross-references Strategist's claims against Scout's evidence. Scores confidence per claim. If overall confidence < 0.6, sends back to Scout with modified search terms (semantic retry). Quality gates between all agents. Max retry limit (3) to prevent infinite loops. | Arbiter catches a low-confidence analysis → triggers re-research with different terms → re-analysis produces higher confidence. |
| **Dev 3** | Pipeline visualization shows retry loops in real-time. Confidence scores displayed on reports. System health panel: active workflows, recent completions, token usage. Competitor configuration UI (add/remove tracked companies). | Dashboard shows the Arbiter sending work back to Scout. Health panel shows system status. |
| **Dev 4** | Token budget system: per-agent and per-workflow caps. Tiered context management: summarize prior agent outputs before passing to next agent. Cost tracking stored in DB, displayed in dashboard. Structured output enforcement (Pydantic) on all LLM calls. | Budget cap triggers graceful stop. Context stays within token limits across 5 agents. |

**Checkpoint:** Full autonomous loop demonstrated:
1. Webhook arrives → Sentinel filters (autonomous decision)
2. Scout researches (real web search, multiple queries)
3. Strategist analyzes (deep reasoning)
4. Arbiter validates → rejects → Scout re-researches with different terms (autonomous retry)
5. Arbiter approves → Scribe generates report
6. All within token budget, all state checkpointed

---

### Phase 3 — Polish & Integrations (Hours 12–16)

**Goal:** Production-quality output and bonus features.

| Dev | Task | Deliverable |
|-----|------|-------------|
| **Dev 1** | PDF report generation (WeasyPrint). Slack webhook notification on report completion. Error handling: graceful degradation on API failures (cached fallback for web search). | Reports downloadable as PDF. Slack notification fires. System doesn't crash when Tavily is down. |
| **Dev 2** | Omium SDK integration: `@omium.trace` on every agent function. Verify causal linking in Omium dashboard (webhook → sentinel → scout → strategist → arbiter → scribe). LangGraph auto-instrumentation. | Omium dashboard shows the complete trace with causal chain. Every tool call visible. |
| **Dev 3** | UI polish: animations (agent activity pulse, pipeline flow), dark mode, typography (Inter font), responsive layout, micro-interactions (hover effects, transitions). Report rendering with syntax-highlighted code blocks, tables, confidence badges. | Dashboard looks premium and impressive. Demo-ready visual quality. |
| **Dev 4** | Demo fixtures: pre-validated webhook payloads. Cached API responses for fallback. `DEMO_MODE=true` environment flag. Golden path testing: run the full pipeline 5+ times, fix any flakiness. | Demo scenario works 100% of the time. Fallback mode available if live APIs fail. |

**Checkpoint:** The product looks and feels polished. Omium dashboard shows full traces. PDF reports generate. Demo scenario is reliable.

---

### Phase 4 — Demo & Submission (Hours 16–20)

**Goal:** Record a flawless 5-minute demo video. Write the 3-page submission document.

| Dev | Task | Deliverable |
|-----|------|-------------|
| **Dev 1** | Final bug fixes. Docker Compose cleanup for clean-machine deployment. README with complete quickstart guide. | `git clone → docker-compose up → working demo` on any machine. |
| **Dev 2** | Final agent tuning: prompt quality, output formatting. Run the pipeline 3+ more times to validate reliability. Omium trace verification. | Agents produce high-quality, consistent outputs. Omium traces are clean. |
| **Dev 3** | Screen recording setup. Record 5-minute demo video following the demo script. Edit if needed for smoothness. | Polished 5-minute video showing the complete autonomous workflow. |
| **Dev 4** | Write 3-page PDF: Problem statement, agent architecture diagram, tool surface, what makes it autonomous, technical decisions. Compile all submission artifacts. | Submission-ready writeup. All artifacts collected. |

**Demo Script (5 minutes):**

| Time | What Happens | What the Audience Sees |
|------|-------------|----------------------|
| 0:00–0:30 | Introduction | Explain the problem: "Competitive intelligence takes analysts hours. ASCENT does it autonomously." |
| 0:30–1:00 | Show the dashboard | Clean, premium UI. Competitor configuration. Empty report list. |
| 1:00–1:30 | Trigger the pipeline | Send a webhook (simulating a news alert about a competitor). Dashboard shows the signal arriving. |
| 1:30–3:30 | Watch agents work | Real-time activity feed shows: Sentinel filtering → Scout searching the web → Strategist analyzing → Arbiter validating → (maybe a retry loop) → Scribe generating report. Pipeline visualization lights up in sequence. |
| 3:30–4:30 | View the result | Complete intelligence report appears. Show executive summary, detailed analysis, source citations, confidence scores. Download PDF. |
| 4:30–5:00 | Show Omium dashboard | Open Omium → show the complete trace: causal chain from webhook to report, every LLM call, every tool invocation, timing and cost data. |

---

### Phase 5 — Buffer (Hours 20–24)

**Goal:** Fix anything broken. Final testing. Submit.

| Dev | Task |
|-----|------|
| **All** | End-to-end testing on a fresh Docker environment. Fix any issues discovered. Final submission. |

---

## Project Structure

```
ascent/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── requirements.txt
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Environment config
│   │
│   ├── api/
│   │   ├── webhooks.py            # POST /webhooks/news, /webhooks/scheduled
│   │   ├── reports.py             # GET /api/reports, GET /api/reports/{id}
│   │   ├── analyze.py             # POST /api/analyze (manual trigger)
│   │   ├── competitors.py         # CRUD /api/competitors
│   │   └── websocket.py           # WebSocket /ws/activity
│   │
│   ├── agents/
│   │   ├── state.py               # PipelineState TypedDict
│   │   ├── graph.py               # LangGraph StateGraph definition
│   │   ├── sentinel.py            # Monitor agent
│   │   ├── scout.py               # Research agent
│   │   ├── strategist.py          # Analysis agent
│   │   ├── arbiter.py             # Validator agent
│   │   ├── scribe.py              # Report agent
│   │   └── tools/
│   │       ├── web_search.py      # Tavily wrapper
│   │       ├── url_scraper.py     # URL content extraction
│   │       └── pdf_generator.py   # PDF report creation
│   │
│   ├── models/
│   │   ├── database.py            # SQLAlchemy/asyncpg setup
│   │   ├── schemas.py             # Pydantic models (structured outputs)
│   │   └── tables.py              # DB table definitions
│   │
│   ├── services/
│   │   ├── budget.py              # Token budget tracking
│   │   ├── context.py             # Tiered context management
│   │   ├── notifications.py       # Slack/email notifications
│   │   └── scheduler.py           # APScheduler for periodic scans
│   │
│   └── tracing/
│       └── omium_setup.py         # Omium SDK initialization
│
├── frontend/
│   ├── index.html                 # Main dashboard page
│   ├── css/
│   │   └── styles.css             # All styles (dark mode, animations)
│   ├── js/
│   │   ├── app.js                 # Main app logic
│   │   ├── websocket.js           # WebSocket connection + activity feed
│   │   ├── pipeline.js            # Pipeline visualization
│   │   ├── reports.js             # Report list + detail rendering
│   │   └── competitors.js         # Competitor CRUD UI
│   └── assets/
│       └── ...
│
└── demo/
    ├── fixtures/                   # Pre-validated webhook payloads
    ├── cached_responses/           # Cached API responses for fallback
    └── demo_script.md             # Step-by-step demo instructions
```

---

## Open Questions

> [!IMPORTANT]
> **Q1: LLM Provider** — Are you set on Gemini 2.0 Flash, or do you have API keys for OpenAI/Anthropic? Gemini Flash is cheapest and fastest but some agents may benefit from stronger reasoning (GPT-4o / Claude for the Strategist).

> [!IMPORTANT]
> **Q2: Target Industry** — ASCENT can track any industry. For the demo, should we pre-configure it for a specific sector (e.g., AI/tech companies, fintech, healthcare)? A focused demo is more compelling than a generic one.

> [!IMPORTANT]
> **Q3: Frontend Preference** — The plan uses vanilla HTML/CSS/JS for speed. If your team's Dev 3 is more productive with React/Next.js, we can switch — but it adds setup overhead.

> [!IMPORTANT]
> **Q4: Omium Access** — Do you have Omium SDK access/API keys? If not, we should sign up now (they have a free tier) so we don't lose the +10% bonus.

> [!IMPORTANT]  
> **Q5: Deployment Target** — The plan assumes local Docker for the demo. Do you want to deploy to a cloud provider (Render, Railway, etc.) for the live judging session, or will you run locally?

---

## Verification Plan

### Automated Tests
- Unit tests on each agent's structured output parsing (Pydantic validation)
- Integration test: webhook → full pipeline → report in DB
- Budget system test: verify pipeline stops at token limit

### Manual Verification
- Run the full demo scenario 10+ times before recording
- Kill the process mid-pipeline, restart, verify checkpoint recovery
- Disconnect internet briefly, verify graceful degradation
- Check Omium dashboard shows complete causal traces
- Test on a fresh Docker environment (simulates judge's machine)
