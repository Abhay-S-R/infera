# ASCENT

**Autonomous Strategic Competitive Event & News Tracker**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4-764ABC)](https://langchain-ai.github.io/langgraph/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ASCENT is a multi-agent intelligence system that continuously monitors competitive signals, autonomously researches and analyzes them, and generates structured intelligence reports — requiring zero human intervention after the initial trigger.

---

## Overview

Modern competitive intelligence requires tracking hundreds of signals across news, product launches, funding rounds, and market shifts. ASCENT automates this entire workflow through a coordinated pipeline of five specialized AI agents:

```
Webhook / Manual Trigger
        │
        ▼
┌─────────────┐     ┌───────────┐     ┌──────────────┐     ┌───────────┐     ┌─────────┐
│  Sentinel   │────▶│   Scout   │────▶│  Strategist  │────▶│  Arbiter  │────▶│  Scribe │
│  (Monitor)  │     │ (Research)│     │  (Analysis)  │     │(Validator)│     │ (Report)│
└─────────────┘     └───────────┘     └──────────────┘     └───────────┘     └─────────┘
     Filter            Web Search        Deep Analysis       Fact-Check        Report
     & Score           & Scrape          & SWOT               & Retry          Generation
```

| Agent | Role |
|-------|------|
| **Sentinel** | Filters incoming signals, scores relevance (0–1), classifies event type |
| **Scout** | Executes web searches via Tavily, scrapes sources, structures raw findings |
| **Strategist** | Synthesizes research into competitive analysis with impact assessments |
| **Arbiter** | Cross-references claims against evidence, triggers re-research if confidence is low |
| **Scribe** | Generates formatted markdown/PDF reports with executive summaries and citations |

### Key Capabilities

- **Autonomous Retry Loops** — Arbiter can reject low-confidence analysis and send it back to Scout with modified search terms
- **Quality Gates** — Confidence checks between every agent transition
- **Token Budget Management** — Per-agent and per-workflow caps to control costs
- **Crash Recovery** — LangGraph + PostgreSQL checkpointing resumes from the last successful agent on failure
- **Real-Time Dashboard** — WebSocket-powered live feed of agent activity and pipeline state

---

## Getting Started

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.12+ |
| Docker & Docker Compose | Latest |
| [Google Gemini API Key](https://aistudio.google.com/apikey) | Required |
| [Tavily API Key](https://tavily.com/) | Required |

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ascent

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Open `.env` and set the required API keys:

```env
GEMINI_API_KEY=<your-gemini-api-key>
TAVILY_API_KEY=<your-tavily-api-key>
```

### Running

**1. Start infrastructure services:**

```bash
docker compose up -d
```

**2. Start the API server:**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**3. Start the frontend:**

```bash
python -m http.server 3000 --directory frontend
```

**4. Verify:**

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

Open `http://localhost:3000` to access the dashboard.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/webhooks/news` | Ingest a news signal and trigger the pipeline |
| `POST` | `/webhooks/scheduled` | Trigger a scheduled competitor scan |
| `POST` | `/api/analyze` | Submit a manual analysis request |
| `GET` | `/api/reports` | List all completed intelligence reports |
| `GET` | `/api/reports/{id}` | Retrieve a specific report |
| `WS` | `/ws/activity` | Subscribe to real-time agent activity events |

---

## Project Structure

```
ascent/
├── docker-compose.yml
├── .env.example
├── requirements.txt
│
├── backend/
│   ├── main.py                     # FastAPI application entry point
│   ├── config.py                   # Environment configuration (Pydantic Settings)
│   │
│   ├── api/
│   │   ├── webhooks.py             # Webhook ingestion endpoints
│   │   ├── reports.py              # Report retrieval endpoints
│   │   ├── analyze.py              # Manual analysis trigger
│   │   ├── competitors.py          # Competitor CRUD operations
│   │   └── websocket.py            # WebSocket activity stream
│   │
│   ├── agents/
│   │   ├── state.py                # LangGraph PipelineState definition
│   │   ├── graph.py                # StateGraph with agent nodes and edges
│   │   ├── sentinel.py             # Signal monitoring and filtering
│   │   ├── scout.py                # Web research and evidence gathering
│   │   ├── strategist.py           # Competitive analysis and insights
│   │   ├── arbiter.py              # Validation and quality assurance
│   │   ├── scribe.py               # Report generation
│   │   └── tools/
│   │       ├── web_search.py       # Tavily search integration
│   │       ├── url_scraper.py      # URL content extraction
│   │       └── pdf_generator.py    # PDF report rendering
│   │
│   ├── models/
│   │   ├── database.py             # Async SQLAlchemy engine and sessions
│   │   ├── tables.py               # Database table definitions
│   │   └── schemas.py              # Pydantic models for agent I/O
│   │
│   └── services/
│       ├── llm.py                  # Gemini API client wrapper
│       ├── logger.py               # Structured JSON logging
│       ├── budget.py               # Token and cost budget tracking
│       ├── context.py              # Tiered context management
│       ├── notifications.py        # Slack / email dispatch
│       └── scheduler.py            # Periodic scan scheduling
│
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── app.js
│       ├── websocket.js
│       ├── pipeline.js
│       ├── reports.js
│       └── competitors.js
│
└── demo/
    ├── fixtures/                   # Sample webhook payloads
    └── cached_responses/           # Cached API responses for offline mode
```

---

## Configuration Reference

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `TAVILY_API_KEY` | Yes | — | Tavily web search API key |
| `DATABASE_URL` | No | `postgresql+asyncpg://ascent:ascent_pass@localhost:5432/ascent_db` | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `OMIUM_API_KEY` | No | — | Omium observability tracing key |
| `SLACK_WEBHOOK_URL` | No | — | Slack webhook for report notifications |
| `DEMO_MODE` | No | `false` | When `true`, uses cached responses instead of live APIs |
| `LOG_LEVEL` | No | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MAX_TOKENS_PER_WORKFLOW` | No | `500000` | Maximum token budget per pipeline execution |
| `MAX_COST_PER_WORKFLOW` | No | `2.00` | Maximum estimated cost (USD) per pipeline execution |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API Framework** | FastAPI with async support |
| **Agent Orchestration** | LangGraph (StateGraph) |
| **LLM** | Google Gemini 2.5 Flash |
| **Web Search** | Tavily API |
| **Database** | PostgreSQL 16 (async via SQLAlchemy + asyncpg) |
| **Cache / Pub-Sub** | Redis 7 |
| **Observability** | Structured JSON logging, Omium SDK |
| **Frontend** | Vanilla HTML/CSS/JS with WebSocket |
| **Infrastructure** | Docker Compose |

---

## License

MIT