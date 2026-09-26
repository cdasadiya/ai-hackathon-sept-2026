#!/usr/bin/env bash
# Quick smoke check for Render deployment (no credentials required).
set -euo pipefail
BASE="${1:-https://ai-hackathon-sept-2026.onrender.com}"

echo "=== Render smoke: $BASE ==="
curl -fsS "$BASE/healthz/" | grep -q '"status": "ok"' && echo "OK healthz"
curl -fsS -o /dev/null -w "home HTTP %{http_code}\n" "$BASE/"
curl -fsS -o /dev/null -w "login HTTP %{http_code}\n" "$BASE/login/"
curl -fsS -o /dev/null -w "register HTTP %{http_code}\n" "$BASE/register/"
admin_code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE/static/admin/css/base.css")
theme_code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE/static/css/nexus-theme.css")
echo "admin static HTTP $admin_code"
echo "nexus-theme.css HTTP $theme_code"
if [[ "$admin_code" != "200" ]]; then
  echo "FAIL: Django static not served — ensure Render buildCommand=./build.sh and startCommand=./scripts/render_start.sh"
  exit 1
fi
if [[ "$theme_code" != "200" ]]; then
  echo "WARN: nexus-theme.css HTTP $theme_code (auth pages use inline CSS fallback)"
fi
curl -fsS "$BASE/" | grep -q "delivered with clarity" && echo "OK home markup" || echo "WARN: home may be an older build"
curl -fsS "$BASE/register/" | grep -q -- "--nx-brand" && echo "OK register auth styles" || echo "FAIL: register missing auth styles"

echo "=== Demo JWT login (requires SEED_DEMO_USERS + deploy with seed on start) ==="
for user in admin1 patient1 doctor1; do
  body=$(curl -fsS -X POST "$BASE/api/token/" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$user\",\"password\":\"Pass1234!\"}" 2>/dev/null || true)
  if echo "$body" | grep -q '"access"'; then
    echo "OK token for $user"
  else
    echo "FAIL token for $user: ${body:-request failed}"
    exit 1
  fi
done

echo "=== Done ==="
