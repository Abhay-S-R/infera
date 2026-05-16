# INFERA

**Autonomous Strategic Competitive Event & News Tracker**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4-764ABC)](https://langchain-ai.github.io/langgraph/)

INFERA is an end-to-end autonomous intelligence system that continuously monitors competitive signals, conducts deep web research, analyzes impact, and delivers structured executive briefings — requiring zero human intervention after the initial trigger.

---

## Why Infera?

Modern competitive intelligence requires tracking hundreds of signals across news, product launches, funding rounds, and market shifts. Traditional analysts spend hours gathering and validating data before they can even begin analysis. 

INFERA automates this entire workflow through a coordinated pipeline of five specialized AI agents. Drop a news link or a Slack message, and within 60 seconds, you receive a fully vetted, multi-page PDF strategy report in your inbox.

---

## The Agent Pipeline

```text
Webhook / Slack / RSS Trigger
        │
        ▼
┌─────────────┐     ┌───────────┐     ┌──────────────┐     ┌───────────┐      ┌─────────┐
│  Sentinel   │────▶│   Scout   │────▶│  Strategist │────▶│  Arbiter  │────▶│  Scribe │
│  (Monitor)  │     │ (Research)│     │  (Analysis)  │     │(Validator)│      │ (Report)│
└─────────────┘     └───────────┘     └──────────────┘     └───────────┘      └─────────┘
     Filter            Web Search        Deep Analysis       Fact-Check        PDF / Email
     & Score           & Scrape          & SWOT               & Retry          Generation
```

| Agent | Role & Capabilities |
|-------|---------------------|
| **Sentinel** | Listens to inbound signals (Slack/Webhooks). Scores relevance (0–1), infers the competitor, and classifies the event type. |
| **Scout** | The researcher. Executes targeted web searches via Tavily, scrapes full-text articles, and structures raw findings. |
| **Strategist** | The analyst. Synthesizes research into competitive analysis, calculating Threat Levels and performing SWOT analysis. |
| **Arbiter** | The skeptic. Cross-references claims against primary evidence. If confidence is low, it halts or loops back to Scout. |
| **Scribe** | Planned publishing layer responsible for formatting intelligence reports, generating PDFs, and dispatching them via Slack & SendGrid. Currently SendGrid is represented in the UI as a disabled/preview feature. |

---

## Key Features

- **Omnichannel Ingress:** Trigger research via REST webhooks, scheduled cron jobs, or simply by `@mentioning` the bot in your Slack workspace.
- **Multi-Channel Delivery:** Final reports are exported as Markdown and PDFs, posted to Slack channels, and emailed to stakeholders via SendGrid.
- **Autonomous Retry Loops:** The Arbiter acts as a quality gate. It will reject hallucinated analysis and force the Scout to dig deeper if sources don't corroborate.
- **Institutional Memory:** Maintains a PostgreSQL-backed profile on every tracked competitor, appending new launches and historical context to inform future analysis.
- **Token Budget Management:** Strict per-agent and per-workflow LLM token caps to guarantee predictable API costs.
- **Real-Time Dashboard:** A sleek, dark-mode dashboard with WebSocket connections to visualize agent thinking and pipeline state in real time.

---

## Getting Started

### Prerequisites

| Requirement | Version | Note |
|-------------|---------|------|
| Python | `3.12+` | Required for advanced async features |
| Docker & Compose | `Latest` | Runs PostgreSQL and Redis |
| [Google Gemini API Key](https://aistudio.google.com/apikey) | `Required`| Core LLM engine |
| [Tavily API Key](https://tavily.com/) | `Required`| Search & scraping |

### Installation

```bash
# Clone the repository
git clone https://github.com/Abhay-S-R/infera.git
cd infera

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

Copy the example environment file:
```bash
cp .env.example .env
```

Open `.env` and configure your API keys. At minimum, you need `GEMINI_API_KEY` and `TAVILY_API_KEY`. See the **Configuration Reference** below for advanced integrations like Slack and SendGrid.

### Running the Stack

**1. Start infrastructure services (PostgreSQL & Redis):**
```bash
docker compose up -d
```

**2. Start the API & Pipeline Engine:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**3. Start the Real-time Dashboard:**
Open a new terminal window and run:
```bash
python -m http.server 3000 --directory frontend
```

**4. Verify:**
Navigate to `http://localhost:3000/index2.html` in your browser. 
To test the API directly:
```bash
curl http://localhost:8000/health
# → {"status": "ok", "components": {...}}
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health and dependency checks |
| `POST` | `/webhooks/news` | Ingest a raw JSON payload/news signal |
| `POST` | `/webhooks/slack/events` | Slack Events API ingress endpoint (handles @mentions) |
| `POST` | `/api/analyze` | Submit a direct, synchronous analysis request |
| `GET` | `/api/reports` | List all completed intelligence reports |
| `GET` | `/api/competitors` | View tracked institutional memory profiles |
| `WS` | `/ws/activity` | WebSocket stream for live agent tracing |

---

## Configuration Reference

| Variable | Required | Description |
|----------|:--------:|-------------|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key used by all agents |
| `TAVILY_API_KEY` | **Yes** | Tavily web search API key used by Scout |
| `DATABASE_URL` | No | `postgresql+asyncpg://infera:infera_pass@localhost:5433/infera_db` |
| `SLACK_WEBHOOK_URL` | No | Slack Incoming Webhook for outbound delivery summaries |
| `SLACK_SIGNING_SECRET` | No | Required if exposing `/webhooks/slack/events` for Slack Ingress |
| `SENDGRID_API_KEY` | No | Required for sending PDF reports via Email |
| `SENDGRID_FROM_EMAIL` | No | Verified sender address for SendGrid |
| `SENDGRID_TO_EMAIL` | No | Target recipient for PDF reports |
| `MAX_COST_PER_WORKFLOW`| No | Hard cap (USD) on API costs per signal execution. Default `2.00` |

---

## Project Structure

```text
infera/
├── backend/
│   ├── agents/          # LangGraph definitions and 5 Agent Node implementations
│   ├── api/             # FastAPI routes (webhooks, health, reports, slack)
│   ├── core/            # Config, DB, Tracing, Token Budgets, Logging
│   ├── integrations/    # LLM wrappers, PDF Generator, SendGrid, Slack
│   ├── models/          # SQLAlchemy tables & Pydantic schemas
│   └── pipeline/        # Background executor, memory profiles, context truncation
├── frontend/            # HTML/JS/CSS WebSocket Dashboard
├── demo/                # Fixtures and DB seeding scripts
└── tests/               # E2E test suites (Pytest)
```