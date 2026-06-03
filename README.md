# INFERA

**Autonomous Strategic Competitive Event & News Tracker**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4-764ABC)](https://langchain-ai.github.io/langgraph/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)

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
| Python | `3.12+` | Backend engine |
| Node.js | `18+` | Frontend development |
| Docker & Compose | `Latest` | PostgreSQL and Redis |
| [Google Gemini API Key](https://aistudio.google.com/apikey) | `Required`| LLM for specific agents |
| [GROQ API Key](https://console.groq.com/) | `Required`| LLM for specific agents |
| [Tavily API Key](https://tavily.com/) | `Required`| Search & scraping |

### Installation

#### Backend Setup

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

# Install Python dependencies
pip install -r requirements.txt
```

#### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Return to project root
cd ..
```

### Configuration

#### Backend Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Open `.env` and configure your API keys. You must provide **both** Google Gemini and GROQ keys, as different agents within the pipeline utilize different LLMs for specific tasks:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

See the **Configuration Reference** below for all available options including Slack and SendGrid integrations.

#### Frontend Configuration

The frontend uses environment variables for API connection:

```bash
cd frontend
# Create .env.local if it doesn't exist
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000
EOF
```

For production, update these URLs to point to your deployed backend.

### Running the Stack

**1. Start infrastructure services (PostgreSQL & Redis):**
```bash
docker compose up -d
```

**2. Start the Backend API & Pipeline Engine:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**3. Start the Next.js Frontend:**
Open a new terminal window and run:
```bash
cd frontend
npm run dev
```

The frontend will start on `http://localhost:3000`

**4. Verify:**

- **Frontend**: Navigate to `http://localhost:3000` for the landing page, or `http://localhost:3000/dashboard` for the main dashboard
- **Backend API**: Test with curl:
  ```bash
  curl http://localhost:8000/health
  # → {"status": "ok", "components": {...}}
  ```

### Production Build

To build the frontend for production:

```bash
cd frontend
npm run build
npm run start
```

This creates an optimized production build served on `http://localhost:3000`

---

## Frontend Features

The Next.js dashboard provides a comprehensive real-time interface for monitoring and managing the intelligence pipeline:

### Landing Page (`/`)
- Hero section with video background
- Feature overview with 4 key capabilities
- Quick launch to dashboard

### Dashboard (`/dashboard`)
- **Manual Analysis Trigger**: Submit competitor analysis requests with custom questions
- **Live Pipeline Visualization**: Real-time view of all 6 agents (Sentinel → Scout → Strategist → Arbiter → Scribe)
  - Status indicators (idle, running, done, error, retry)
  - Animated pulse effects for active agents
  - Retry loop visualization (Arbiter → Scout)
- **System Health Panel**: Active workflows, total reports, recent completions
- **Competitor Management**: Add, remove, and track competitors
- **Activity Feed**: 
  - Real-time WebSocket updates
  - Agent status changes and events
  - Arbiter/Verifier rejection alerts
  - Delivery events with channel status (Slack, Email, Webhook)
  - Auto-scroll with event history (last 100 events)

### Reports Page (`/dashboard/reports`)
- Grid view of all intelligence reports
- Confidence badges (HIGH/MED/LOW) with color coding
- Click-to-view detailed reports with 4 audience-specific tabs:
  - **Executive**: Strategic overview for C-suite
  - **Technical**: Deep technical analysis
  - **Sales**: Revenue opportunities and positioning
  - **Risk**: Threat assessment and mitigation
- Markdown rendering with safe HTML-free parsing
- Empty and error state handling

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

### LLM Providers (Both Required)

| Variable | Required | Description |
|----------|:--------:|-------------|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key - Get from [Google AI Studio](https://aistudio.google.com/apikey) |
| `GROQ_API_KEY` | **Yes** | GROQ API key - Get from [GROQ Console](https://console.groq.com/) |

**Note**: You must provide **both** API keys, as some agents specifically require Gemini while others rely on Groq.

### Required Services

| Variable | Required | Description |
|----------|:--------:|-------------|
| `TAVILY_API_KEY` | **Yes** | Tavily web search API key used by Scout agent |

### Database & Infrastructure

| Variable | Required | Description |
|----------|:--------:|-------------|
| `DATABASE_URL` | No | Default: `postgresql+asyncpg://infera:infera_pass@localhost:5433/infera_db` |

### Optional Integrations

| Variable | Required | Description |
|----------|:--------:|-------------|
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
├── frontend/            # Next.js + React + TypeScript Dashboard
│   ├── app/            # Next.js App Router pages
│   │   ├── page.tsx           # Landing page
│   │   └── dashboard/         # Dashboard routes
│   │       ├── page.tsx       # Main dashboard
│   │       └── reports/       # Reports page
│   ├── components/     # React components
│   │   ├── dashboard/         # Dashboard components
│   │   ├── landing/           # Landing page components
│   │   └── reports/           # Report components
│   ├── hooks/          # Custom React hooks (WebSocket, etc.)
│   ├── lib/            # Utilities and API client
│   └── public/         # Static assets
├── demo/                # Fixtures and DB seeding scripts
└── docs/                # Documentation
```

## Technology Stack

### Backend
- **Python 3.12+** - Core language
- **FastAPI** - High-performance async web framework
- **LangGraph** - Agent orchestration and state management
- **PostgreSQL** - Persistent storage for reports and competitor profiles
- **Redis** - Task queue and caching
- **Google Gemini & GROQ** - LLMs for agent reasoning (both required for different agents)
- **Tavily** - Web search and content extraction

### Frontend
- **Next.js 16** - React framework with App Router
- **React 19** - UI library
- **TypeScript 5** - Type safety
- **CSS Modules** - Scoped styling
- **WebSocket** - Real-time activity updates