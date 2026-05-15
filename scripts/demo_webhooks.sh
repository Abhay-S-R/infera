#!/usr/bin/env bash
# Demo webhook curls for Phase 4 — requires API on :8000
set -euo pipefail
API="${API:-http://127.0.0.1:8000}"

echo "=== 1. Golden path — Nimbus AI (should verify + run full pipeline) ==="
curl -s -X POST "$API/webhooks/news" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Nimbus AI announces Orion enterprise analytics platform with AI orchestration",
    "source": "golden_path",
    "competitor_name": "Nimbus AI",
    "content": "Nimbus AI unveiled Orion. Pricing unknown. Seeded demo competitor."
  }' | jq .

echo ""
echo "=== 2. Fake rumor (should HALT at Verifier) ==="
curl -s -X POST "$API/webhooks/news" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "BREAKING: OpenAI acquires Anthropic for $500B effective immediately",
    "source": "demo",
    "competitor_name": "Anthropic",
    "content": "Unverified rumor for demo — should be rejected by Verifier."
  }' | jq .

echo ""
echo "=== 3. Competitor institutional memory ==="
curl -s "$API/api/competitors/Nimbus%20AI/profile" | jq .
