#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .dev
docker compose up -d --wait --wait-timeout 60
.venv/bin/python manage.py migrate --noinput
mkdir -p .runtime
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
trap 'exit 130' INT TERM
.venv/bin/celery -A config worker --pool=solo --concurrency=1 --loglevel=INFO >.runtime/worker.log 2>&1 &
pids+=("$!")
.venv/bin/celery -A config beat --schedule .runtime/celerybeat-schedule --pidfile= --loglevel=INFO >.runtime/beat.log 2>&1 &
pids+=("$!")
.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload >.runtime/web.log 2>&1 &
pids+=("$!")
echo 'Django, Celery worker and beat started; logs are in .runtime/. Ctrl-C stops these processes.'
wait -n "${pids[@]}"
exit 1
