#!/usr/bin/env bash
# One image, three roles. Kubernetes picks the role via the container's args.
set -euo pipefail
case "${1:-api}" in
  api)    exec uvicorn api:app --host 0.0.0.0 --port 8000 ;;
  worker) exec python worker.py ;;
  reaper) exec python reaper.py ;;
  *)      echo "unknown role: ${1}"; exit 1 ;;
esac
