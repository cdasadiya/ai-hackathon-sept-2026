#!/usr/bin/env bash
# Production URL audit for NexusHealth on Render (read-only, no credentials).
set -u
BASE="${1:-https://ai-hackathon-sept-2026.onrender.com}"
PASS=0
FAIL=0
WARN=0

check() {
  local method="$1" path="$2" expect="$3" note="$4"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" -X "$method" --max-time 120 "${BASE}${path}")
  if [[ "$code" == "$expect" ]]; then
    echo "PASS $method $path -> $code ($note)"
    PASS=$((PASS + 1))
  else
    echo "FAIL $method $path -> $code expected $expect ($note)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Production URL audit: $BASE ==="
check GET / 200 "home"
check GET /login/ 200 "login"
check GET /register/ 200 "register"
check GET /healthz/ 200 "health"
check GET /password-reset/ 200 "password reset"
check GET /patient/dashboard/ 302 "patient dashboard auth redirect"
check GET /doctor/dashboard/ 302 "doctor dashboard auth redirect"
check GET /dashboard/admin/ 302 "admin dashboard auth redirect"
check GET /upload-report/ 302 "upload auth redirect"
check GET /debug-admin/ 302 "debug admin auth redirect"
check GET /does-not-exist-xyz/ 404 "404 page"
check POST /api/token/ 400 "JWT requires JSON body"
check GET /api/token/ 405 "JWT GET not allowed"

html=$(curl -fsS --max-time 120 "${BASE}/register/")
if echo "$html" | grep -q -- "--nx-brand"; then
  echo "PASS register inline auth CSS present"
  PASS=$((PASS + 1))
else
  echo "FAIL register missing inline auth CSS"
  FAIL=$((FAIL + 1))
fi

admin_static=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 60 "${BASE}/static/admin/css/base.css")
css_code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 60 "${BASE}/static/css/nexus-theme.css")
if [[ "$admin_static" == "200" ]]; then
  echo "PASS static admin base.css"
  PASS=$((PASS + 1))
else
  echo "FAIL static admin base.css HTTP $admin_static (run ./scripts/render_start.sh on Render)"
  FAIL=$((FAIL + 1))
fi
if [[ "$css_code" == "200" ]]; then
  echo "PASS static nexus-theme.css"
  PASS=$((PASS + 1))
else
  echo "WARN static nexus-theme.css HTTP $css_code (inline CSS should still style auth)"
  WARN=$((WARN + 1))
fi

echo "=== Summary: PASS=$PASS FAIL=$FAIL WARN=$WARN ==="
[[ "$FAIL" -eq 0 ]]
