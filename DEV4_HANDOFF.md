# Dev 4 Handoff — After Dev 2 Foundation Push

Rebase onto Dev 2's branch. **Only edit these files:**

- `backend/agents/sentinel.py`
- `backend/agents/scout.py`
- `backend/agents/strategist.py`
- `backend/agents/scribe.py`
- `backend/agents/arbiter.py` (optional prompt tweak)

**Do not edit:** `schemas.py` (types already added), `tables.py`, `context.py`, `state.py`, `verifier.py`, `graph.py`, `background.py`.

---

## Dev 2 follow-up (after foundation)

- `profile_loader` node: Sentinel → **profile_loader** → Verifier → Scouts
- `state["competitor_context"]` — formatted memory block (use in Scout/Strategist prompts)
- `golden_path` source → verifier uses **seeded profile**, not random "Orion" web hits
- `GET /api/competitors/{name}/profile` — institutional memory API
- `verifier.rejected` WebSocket event + UI banner
- `demo/fixtures/golden_path.py`, `scripts/demo_webhooks.sh`

## What Dev 2 gave you

### Read from state

```python
profile = state.get("competitor_profile")  # CompetitorProfile | None
context = state.get("competitor_context")  # str prompt block — inject into Scout/Strategist
verification = state.get("verification_output")  # set by Verifier — don't re-verify
```

### Prompt helper

```python
from backend.services.context import competitor_profile_prompt_block

block = competitor_profile_prompt_block(state.get("competitor_profile"))
# Inject into Sentinel + Strategist system/user prompts
```

### Sentinel

- Set `resolved_competitor` on `SentinelOutput` when you detect the company
- Use `competitor_profile_prompt_block(profile)` in prompt

### Scout

- Step 1: `generate_structured(..., response_model=ResearchAgenda)`
- Step 2: search each `question.question` (not keyword variants)
- Set `research_output.agenda` on final `ResearchOutput`

### Strategist

- Use `competitor_profile_prompt_block` instead of `get_competitor_history` titles only
- Fill `ceo_qa_pairs: list[CeoQaPair]` with **5** meeting Q&As (question + answer + confidence)
- Keep `InsightType` on every insight

### Scribe

- Enforce exec ≤220 words, tech ~500 words, sales bullets, risk table
- Render confidence: ✅ CONFIRMED / ⚠️ *INFERRED* / ❓ SPECULATIVE
- Exec brief ends with `## Likely CEO Questions` from `ceo_qa_pairs`

---

## Demo seed (Dev 2)

```bash
.venv/bin/python demo/fixtures/seed_column4_demo.py
```

Use competitor name **`Nimbus AI`** in manual analyze / webhooks.

## Tests

```bash
.venv/bin/python -m pytest tests/test_phase4_dev2_foundation.py -v
```

Dev 4 adds: `tests/test_phase4_dev4_agents.py`
