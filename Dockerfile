FROM python:3.14.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN chmod +x build.sh scripts/render_start.sh \
    && DATABASE_URL=sqlite:////tmp/collectstatic.sqlite3 SECRET_KEY=docker-build-only \
       python manage.py collectstatic --no-input

EXPOSE 8000

CMD ["bash", "scripts/render_start.sh"]
