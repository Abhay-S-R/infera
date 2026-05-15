# Column 4 — Manual Testing Guide (Dev 2 + Dev 4)

## Quick answer: conflicts?

**No file conflicts.** Dev 4 edited only agent brains; Dev 2 owns graph, verifier, profile DB, background.

| Area | Dev 2 | Dev 4 | Integrated? |
|------|-------|-------|-------------|
| Schemas (`VerificationOutput`, `CompetitorProfile`, `ceo_qa_pairs`, `ResearchAgenda`) | Added | Uses | Yes |
| `state.competitor_profile` | Yes | Sentinel, Scout, Strategist read | Yes |
| `state.competitor_context` | Yes | Redundant with profile; harmless | Yes |
| `profile_loader` node | Yes | Runs before Verifier | Yes |
| `competitor_profile_prompt_block()` | Yes | Sentinel, Scout, Strategist | Yes |
| `get_competitor_history()` | Legacy | Strategist no longer uses | OK |

**Automated:** `pytest` — 15/15 passed (Dev2 + Dev4 tests).

**Fixed during review:** Scribe/Strategist had literal `\\n` instead of newlines in CEO Q&A block (now fixed).

---

## One-command smoke test (offline + DB)

```bash
cd ~/projects/ascent
docker compose up -d
chmod +x scripts/manual_test_column4.sh scripts/test_phase4_dev2.sh scripts/demo_webhooks.sh
./scripts/manual_test_column4.sh
```

---

## All manual tests (run in order)

### A. Offline (no API cost)

```bash
# 1. Unit tests
.venv/bin/python -m pytest tests/test_phase4_dev2_foundation.py tests/test_phase4_dev4_agents.py -v

# 2. Graph order
.venv/bin/python -c "
from backend.agents.graph import build_graph
print(list(build_graph().get_graph().nodes.keys()))
"

# 3. Dev 2 infra (DB, PDF, seed)
./scripts/test_phase4_dev2.sh
```

### B. Database + API

```bash
# 4. Seed fictional demo competitor
.venv/bin/python demo/fixtures/seed_column4_demo.py

# 5. Start API (terminal 1)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Profile API (terminal 2)
curl -s http://127.0.0.1:8000/api/competitors/Nimbus%20AI/profile | jq '.found, .launch_history | length'
# Expect: true, 2

# 7. Health
curl -s http://127.0.0.1:8000/health | jq .
```

### C. End-to-end pipeline (uses APIs)

```bash
# 8. Golden path — primary demo (source=golden_path, seeded verifier)
.venv/bin/python demo/fixtures/seed_column4_demo.py
.venv/bin/python demo/fixtures/golden_path.py

# 9. Second run — profile write-back should enrich DB
.venv/bin/python demo/fixtures/golden_path.py --run-number 2
curl -s http://127.0.0.1:8000/api/competitors/Nimbus%20AI/profile | jq '.launch_history | length'

# 10. Live test (optional; needs Groq quota)
./scripts/test_phase4_dev2.sh --live --live-nimbus-only
```

### D. Webhooks + UI

```bash
# 11. Webhooks (server running)
./scripts/demo_webhooks.sh

# 12. Frontend (terminal 3)
python -m http.server 3000 --directory frontend
# Open index2.html — watch pipeline: Sentinel → Verifier → Scout → ...
# Reports tab: Exec / Tech / Sales / Risk
```

### E. Verifier halt (fake rumor)

```bash
curl -s -X POST http://127.0.0.1:8000/webhooks/news \
  -H "Content-Type: application/json" \
  -d '{
    "title": "FAKE: OpenAI acquires Anthropic for $500B",
    "source": "test",
    "competitor_name": "Anthropic",
    "content": "Unverified rumor for testing."
  }'
# Expect: workflow rejected at Verifier (activity feed red banner)
```

---

## What to verify in golden path output

| Check | Pass criteria |
|-------|----------------|
| Verifier | `verified=True`, reasoning mentions **seeded institutional memory** |
| Scouts | Log `scout_agenda_generated` with **English questions** (not keyword spam) |
| Strategist | `ceo_qa_pairs` count ≥ 3 (target 5) |
| Scribe | Exec brief has `## Decision Needed`, `## Likely CEO Questions`, confidence markers |
| Reports | 4 tabs populated in UI |
| PDF | `reports_output/report_golden-path-001.pdf` exists |
| Profile | After run 2, `launch_history` may grow |

---

## Known limitations (not merge bugs)

1. **Nimbus AI is fictional** — web search may still find homonym "Orion" companies; use `source=golden_path` + seed for demo.
2. **Groq daily limit** — Sentinel/Scout agenda use Groq; if 429, wait or use `golden_path.py` (verifier uses Gemini + seed bypass).
3. **Exec brief length** — LLM may exceed 220 words; Scribe post-process does not hard-truncate yet.

---

## If something fails

| Symptom | Fix |
|---------|-----|
| DB connection refused | `docker compose up -d` |
| Verifier rejects golden path | Run seed script; ensure `source=golden_path` |
| Groq 429 everywhere | Wait ~30 min or run offline tests only |
| Empty reports | Check `GEMINI_API_KEY`, `TAVILY_API_KEY` in `.env` |
| jq not found | `sudo apt install jq` or use raw `curl` |
