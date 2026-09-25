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

echo "=== Running database migrations ==="
python manage.py migrate --no-input --verbosity 2

echo "=== Checking migration status ==="
python manage.py showmigrations

if [ "${SEED_DEMO_USERS:-true}" = "true" ]; then
  echo "=== Seeding demo users ==="
  python manage.py seed_demo_users
else
  echo "=== Skipping demo user seed (SEED_DEMO_USERS=false) ==="
fi

echo "=== Build complete ==="
