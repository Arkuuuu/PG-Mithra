#!/bin/sh

echo "============================================================"
echo "🚀 Container boot: Initializing PG Scraper & Map Dashboard"
echo "============================================================"

# Ensure directories are created
mkdir -p /app/output

# Start local map server in background (runs index.html)
python server.py &

# Start scraper loop in foreground (infinite loop mode, default cooldown 30 mins)
python main.py --loop --loop-interval 1800
