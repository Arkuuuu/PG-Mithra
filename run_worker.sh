#!/bin/bash
echo "============================================================"
echo "[AUTO-UPDATE] Checking for code updates from GitHub..."
echo "============================================================"
git pull
if [ $? -ne 0 ]; then
    echo "[WARNING] Could not check for updates. Starting worker anyway..."
fi
echo ""
echo "============================================================"
echo "[START] Launching Scraper Bot Farm Worker Loop..."
echo "============================================================"
python3 main.py --loop --loop-interval 600
