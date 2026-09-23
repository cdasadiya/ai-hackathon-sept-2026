#!/usr/bin/env bash
set -o errexit

echo "=== Installing dependencies ==="
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Running database migrations ==="
python manage.py migrate --no-input --verbosity 2

echo "=== Checking migration status ==="
python manage.py showmigrations

echo "=== Seeding demo users ==="
python manage.py seed_demo_users

echo "=== Build complete ==="
