#!/bin/zsh
# Keep the Vexo band bridge alive for the whole demo: restarts it if it ever exits.
cd "$(dirname "$0")"
while true; do
  .venv/bin/python -u -m backend.band_bridge --band "${1:-17}" --follow "${@:2}"
  echo "$(date +%H:%M:%S) bridge exited; restarting in 1s"; sleep 1
done
