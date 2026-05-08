#!/bin/bash
# UK E-commerce Scraper Launcher
# Restarts automatically if it crashes

SESSION="uk-ecom-scraper"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/home/expertfox/.openclaw/workspace/uk_ecom_data"

mkdir -p "$LOG_DIR"

echo "[$(date)] Starting UK e-commerce scraper..." >> "$LOG_DIR/run.log"

while true; do
    python3 "$SCRIPT_DIR/scraper.py" 2>&1
    EXIT_CODE=$?
    echo "[$(date)] Scraper exited with code $EXIT_CODE. Restarting in 30s..." >> "$LOG_DIR/run.log"
    echo ""
    echo "  ⚠  Scraper stopped (exit $EXIT_CODE). Auto-restarting in 30 seconds..."
    sleep 30
done
