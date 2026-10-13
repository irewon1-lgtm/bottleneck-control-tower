#!/usr/bin/env bash
set -euo pipefail
cd /workspace/bottleneck-control-tower
export PIP_CACHE_DIR=/workspace/bct-v4-cache/pip
if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check \
  --extra-index-url https://download.pytorch.org/whl/cpu -r scripts/v4/requirements.lock
.venv/bin/python -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -m bct.v4 --root var/v4/runtime prepare-model
