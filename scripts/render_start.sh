#!/usr/bin/env bash
# Render web service start: static assets, migrations, Gunicorn.
set -euo pipefail

echo "=== collectstatic ==="
python manage.py collectstatic --no-input
if [ ! -f staticfiles/admin/css/base.css ]; then
  echo "ERROR: Django admin static missing after collectstatic"
  exit 1
fi
if [ ! -f staticfiles/css/nexus-theme.css ]; then
  echo "ERROR: staticfiles/css/nexus-theme.css missing after collectstatic"
  exit 1
fi

echo "=== migrate ==="
python manage.py migrate --no-input

echo "=== demo users (production Postgres) ==="
./scripts/seed_demo_if_enabled.sh

echo "=== gunicorn ==="
PORT="${PORT:-8000}"
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}" --log-file - --workers 2 --timeout 120
