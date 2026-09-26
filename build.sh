#!/usr/bin/env bash
set -o errexit

echo "=== Installing dependencies ==="
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input
if [ ! -f staticfiles/css/nexus-theme.css ]; then
  echo "ERROR: staticfiles/css/nexus-theme.css missing after collectstatic"
  exit 1
fi

echo "=== Running database migrations (build) ==="
if [ -n "${DATABASE_URL:-}" ]; then
  python manage.py migrate --no-input --verbosity 2
else
  echo "Skipping migrate at build: DATABASE_URL not set"
fi

echo "=== Checking migration status ==="
python manage.py showmigrations

echo "=== demo users (build; skipped if no DATABASE_URL) ==="
./scripts/seed_demo_if_enabled.sh

echo "=== Build complete ==="
