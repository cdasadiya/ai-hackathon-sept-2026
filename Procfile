web: python manage.py collectstatic --no-input && python manage.py migrate --no-input && gunicorn config.wsgi:application --log-file - --workers 2 --timeout 120
