#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${NETLIFY:-}" == "true" ]]; then
  [[ "${BRANCH:-}" == "codex/bct-v4-integration" ]] || { echo "Deployment branch rejected"; exit 1; }
  [[ "${CONTEXT:-}" == "production" ]] || { echo "Preview publication is disabled"; exit 1; }
fi
export PYTHONPATH=src
python3 -m pip install --disable-pip-version-check -e . 'pytest>=8,<9'
python3 -m pytest -q tests/test_v4_dashboard.py tests/test_v4_dashboard_research_sync.py
node --test tests/test_readable_view_model.js tests/test_future_ui_clarity.js
python3 tools/v4_dashboard_hosting.py --output var/v4/netlify
mkdir -p var/v4/netlify/functions/dashboard var/v4/netlify/public
cp var/v4/netlify/worker/index.js var/v4/netlify/functions/dashboard/snapshot.mjs
cp deploy/v4-dashboard/dashboard.mjs var/v4/netlify/functions/dashboard/dashboard.mjs
node tools/v4_dashboard_release_check.mjs var/v4/netlify/worker/index.js
node tools/v4_dashboard_access_check.mjs var/v4/netlify/functions/dashboard/dashboard.mjs
# The public directory contains no research data or application assets.
printf '%s\n' 'Private origin. Use the owner-private ChatGPT Site.' > var/v4/netlify/public/404.html
echo "Test gate passed; Netlify may publish this immutable version."
