#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-/workspace/.cache/uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/workspace/.python}"
if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.11 .venv
fi
uv pip sync --python .venv/bin/python requirements.txt
mkdir -p .dev
docker compose up -d --wait --wait-timeout 60
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py check
