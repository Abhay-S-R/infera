### ⏳ What is LEFT to build for Phase 0
To finish Phase 0, we need to complete the following:

*1. Dev 1 (API & Database Foundation):*
*   backend/models/database.py (SQLAlchemy async engine setup)
*   backend/models/tables.py (Database tables)
*   backend/main.py (FastAPI app skeleton with health check)

*2. Dev 2 (Agent Graph Skeleton):*
*   backend/agents/state.py (LangGraph state definition)
*   backend/agents/graph.py (Empty LangGraph connecting the 5 agents)
*   backend/agents/tools/web_search.py & url_scraper.py (Tool stubs)

*3. Dev 3 (Frontend Skeleton):*
*   frontend/index.html & frontend/css/styles.css (Dashboard layout)
*   frontend/js/app.js, websocket.js, pipeline.js (Basic frontend logic)

*4. Dev 4 (Utilities):*
*   backend/services/llm.py (Gemini API wrapper)
*   backend/services/logger.py (Structured logging)
*   README.md (Quickstart guide)

Once these files are created, we hit our *Hour 2 Sync Point*: docker compose up works, the FastAPI server runs at localhost:8000/health, the frontend loads at localhost:3000, and the empty LangGraph can execute.