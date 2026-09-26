#!/usr/bin/env bash
# Quick smoke check for Render deployment (no credentials required).
set -euo pipefail
BASE="${1:-https://ai-hackathon-sept-2026.onrender.com}"

echo "=== Render smoke: $BASE ==="
curl -fsS --max-time 120 "$BASE/healthz/" | grep -q '"status": "ok"' && echo "OK healthz"
curl -fsS -o /dev/null -w "home HTTP %{http_code}\n" --max-time 120 "$BASE/"
curl -fsS -o /dev/null -w "login HTTP %{http_code}\n" --max-time 60 "$BASE/login/"
curl -fsS -o /dev/null -w "register HTTP %{http_code}\n" --max-time 60 "$BASE/register/"
admin_code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 60 "$BASE/static/admin/css/base.css")
theme_code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 60 "$BASE/static/css/nexus-theme.css")
echo "admin static HTTP $admin_code"
echo "nexus-theme.css HTTP $theme_code"
if [[ "$admin_code" != "200" ]]; then
  echo "FAIL: Django static not served — ensure Render buildCommand=./build.sh and startCommand=./scripts/render_start.sh"
  exit 1
fi
if [[ "$theme_code" != "200" ]]; then
  echo "WARN: nexus-theme.css HTTP $theme_code (auth pages use inline CSS fallback)"
fi

# Write to temp files so grep closing the pipe early does not trip curl (23) under pipefail.
home_html=$(mktemp)
reg_html=$(mktemp)
trap 'rm -f "$home_html" "$reg_html"' EXIT
curl -fsS --max-time 60 "$BASE/" -o "$home_html"
if grep -q "delivered with clarity" "$home_html"; then
  echo "OK home markup"
else
  echo "WARN: home may be an older build"
fi
curl -fsS --max-time 60 "$BASE/register/" -o "$reg_html"
if grep -q -- "--nx-brand" "$reg_html"; then
  echo "OK register auth styles"
else
  echo "FAIL: register missing auth styles"
  exit 1
fi

echo "=== Demo JWT login (requires SEED_DEMO_USERS + deploy with seed on start) ==="
SMOKE_FAIL=0
for user in patient1 doctor1; do
  body=$(curl -sS --max-time 60 -X POST "$BASE/api/token/" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$user\",\"password\":\"Pass1234!\"}" || true)
  if echo "$body" | grep -q '"access"'; then
    echo "OK token for $user"
  else
    echo "FAIL token for $user: ${body:-request failed}"
    SMOKE_FAIL=1
  fi
done

# admin1 is created by seed_demo_users on container start. If Render has not
# redeployed or SEED_DEMO_USERS=false, treat as WARN (not a hard smoke failure).
admin_body=$(curl -sS --max-time 60 -X POST "$BASE/api/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"Pass1234!"}' || true)
if echo "$admin_body" | grep -q '"access"'; then
  echo "OK token for admin1"
else
  echo "WARN token for admin1 missing (redeploy with SEED_DEMO_USERS=true to create demo admins)"
fi

if [[ "$SMOKE_FAIL" -ne 0 ]]; then
  exit 1
fi
echo "=== Done ==="
