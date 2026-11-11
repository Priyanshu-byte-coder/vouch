# Vouch API image. Built by deploy/docker-compose.yml.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# ROOT in app/config.py resolves to /srv/vouch; the cache volume holds the SQLite cache and the Retraction Watch CSV
WORKDIR /srv/vouch/backend
COPY requirements.lock .
RUN pip install -r requirements.lock
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
