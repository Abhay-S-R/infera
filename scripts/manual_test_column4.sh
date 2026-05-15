#!/usr/bin/env bash
# Column 4 — full manual verification (Dev 2 + Dev 4 integration)
# Run from repo root: ./scripts/manual_test_column4.sh
# Optional: ./scripts/manual_test_column4.sh --live   (uses APIs — needs keys + Groq quota)
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
LIVE=false
if [[ "${1:-}" == "--live" ]]; then
  LIVE=true
fi

echo "=============================================="
echo "  ASCENT Column 4 — Manual Verification"
echo "  Dev 2 (infra) + Dev 4 (agents) integration"
echo "=============================================="
echo ""

# ─── 0. Prerequisites ───
echo ">>> [0] Prerequisites"
if [[ ! -x "$PY" ]]; then PY=python3; fi
echo "    Python: $PY"
docker compose ps 2>/dev/null | head -5 || echo "    (docker compose ps unavailable)"
echo ""

# ─── 1. Unit tests (no APIs) ───
echo ">>> [1] Unit tests (offline)"
$PY -m pytest tests/test_phase4_dev2_foundation.py tests/test_phase4_dev4_agents.py -v --tb=short
echo ""

# ─── 2. Graph structure ───
echo ">>> [2] LangGraph node order"
$PY -c "
from backend.agents.graph import build_graph
nodes = list(build_graph().get_graph().nodes.keys())
expected = ['__start__', 'sentinel', 'profile_loader', 'verifier', 'scout', 'strategist', 'arbiter', 'scribe', '__end__']
assert nodes == expected, f'Expected {expected}, got {nodes}'
print('    OK:', ' -> '.join(n for n in nodes if not n.startswith('__')))
"
echo ""

# ─── 3. Dev 2 foundation script ───
echo ">>> [3] Dev 2 foundation (DB + PDF + seed)"
$PY scripts/test_phase4_dev2.py
echo ""

# ─── 4. Seed demo competitor ───
echo ">>> [4] Seed Nimbus AI institutional memory"
$PY demo/fixtures/seed_column4_demo.py
echo ""

# ─── 5. Profile API (server must be running) ───
echo ">>> [5] Profile API (skip if server down)"
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  curl -sf "http://127.0.0.1:8000/api/competitors/Nimbus%20AI/profile" | $PY -m json.tool 2>/dev/null | head -20 || curl -sf "http://127.0.0.1:8000/api/competitors/Nimbus%20AI/profile"
  echo ""
else
  echo "    SKIP: start server with: uvicorn backend.main:app --port 8000"
  echo ""
fi

# ─── 6. Golden path (CLI pipeline, uses APIs) ───
echo ">>> [6] Golden path pipeline (APIs — Gemini/Tavily/Groq)"
echo "    This is the main end-to-end demo. May take 5-15 min."
read -r -p "    Run golden_path.py now? [y/N] " ans
if [[ "${ans,,}" == "y" ]]; then
  $PY demo/fixtures/golden_path.py
  echo ""
  $PY demo/fixtures/golden_path.py --run-number 2
else
  echo "    Skipped. Run manually: $PY demo/fixtures/golden_path.py"
fi
echo ""

# ─── 7. Optional live test suite ───
if $LIVE; then
  echo ">>> [7] Live test suite (--live)"
  ./scripts/test_phase4_dev2.sh --live --live-nimbus-only
else
  echo ">>> [7] Live tests skipped (pass --live to enable)"
fi
echo ""

# ─── 8. Webhook curls (server must be running) ───
echo ">>> [8] Webhook manual tests (optional)"
echo "    With server running:"
echo "      ./scripts/demo_webhooks.sh"
echo ""

echo "=============================================="
echo "  Manual checklist complete"
echo "=============================================="
