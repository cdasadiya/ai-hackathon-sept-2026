#!/usr/bin/env bash
# Seed demo users into the active database. On Render, DATABASE_URL is reliable at
# runtime (start) but often missing during build — do not rely on build-only seed.
set -euo pipefail

if [ "${SEED_DEMO_USERS:-true}" != "true" ] && [ "${SEED_DEMO_USERS:-true}" != "True" ] && [ "${SEED_DEMO_USERS:-true}" != "1" ] && [ "${SEED_DEMO_USERS:-true}" != "yes" ]; then
  echo "=== Skipping demo user seed (SEED_DEMO_USERS=${SEED_DEMO_USERS:-true}) ==="
  exit 0
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "=== Skipping demo user seed: DATABASE_URL not set ==="
  exit 0
fi

echo "=== Seeding demo users ==="
python manage.py seed_demo_users
