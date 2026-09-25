#!/usr/bin/env bash
# Quick smoke check for Render deployment (no credentials required).
set -euo pipefail
BASE="${1:-https://ai-hackathon-sept-2026.onrender.com}"

echo "=== Render smoke: $BASE ==="
curl -fsS "$BASE/healthz/" | grep -q '"status": "ok"' && echo "OK healthz"
curl -fsS -o /dev/null -w "home HTTP %{http_code}\n" "$BASE/"
curl -fsS -o /dev/null -w "login HTTP %{http_code}\n" "$BASE/login/"
curl -fsS -o /dev/null -w "register HTTP %{http_code}\n" "$BASE/register/"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE/static/css/nexus-theme.css")
echo "nexus-theme.css HTTP $code"
if [[ "$code" != "200" ]]; then
  echo "FAIL: static CSS missing — run collectstatic on deploy (build.sh) and redeploy latest main."
  exit 1
fi
curl -fsS "$BASE/" | grep -q "delivered with clarity" && echo "OK new home markup" || echo "WARN: home may still be an older build"
echo "=== Done ==="
