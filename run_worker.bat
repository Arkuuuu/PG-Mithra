@echo off
title Google Maps Scraper Worker Node
echo ============================================================
echo [AUTO-UPDATE] Checking for code updates from GitHub...
echo ============================================================
git pull
if %errorlevel% neq 0 (
    echo [WARNING] Could not check for updates (is Git configured?). Starting worker anyway...
)
echo.
echo ============================================================
echo [START] Launching Scraper Bot Farm Worker Loop...
echo ============================================================
python main.py --loop --loop-interval 600
pause
