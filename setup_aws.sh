#!/bin/bash
# ─────────────────────────────────────────────────────────────
# AWS EC2 / Linux VPS Automated Setup Script for 24/7 PG Scraper
# ─────────────────────────────────────────────────────────────
set -e

echo "🚀 Starting AWS EC2 / Linux VPS 24/7 Environment Setup..."

# 1. Update system package repositories & Configure 2GB Swap for AWS Free Tier (1GB RAM)
echo "🧹 Optimizing System & Configuring 2GB Swap Memory..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl wget build-essential

if [ ! -f /swapfile ]; then
    echo "💾 Creating 2GB Swap Space for 1GB RAM Free Tier..."
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ Swap Memory configured successfully."
fi

# 2. Install Playwright system dependencies (Chromium libs)
echo "📦 Installing Playwright Linux System Dependencies..."
sudo apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    librandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2

# 3. Set up Python Virtual Environment
echo "🐍 Creating Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Python Requirements
pip install --upgrade pip
pip install playwright supabase python-dotenv beautifulsoup4 requests pandas

# 5. Install Playwright Chromium Browser
echo "🌐 Installing Playwright Chromium Browser..."
playwright install chromium
playwright install-deps

# 6. Setup Systemd Auto-Healing Service
echo "⚙️ Configuring Systemd Service (pg-scraper.service)..."
APP_DIR=$(pwd)
USER_NAME=$(whoami)

cat <<EOF | sudo tee /etc/systemd/system/pg-scraper.service
[Unit]
Description=24/7 PG Scraper & Auto-Updater Daemon Node
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/python auto_updater.py
Restart=always
RestartSec=5s
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 7. Reload systemd daemon & enable service
sudo systemctl daemon-reload
sudo systemctl enable pg-scraper.service

echo "=================================================================="
echo "✅ AWS EC2 Environment Setup Complete!"
echo "=================================================================="
echo "To start the 24/7 worker node service, run:"
echo "  sudo systemctl start pg-scraper.service"
echo "To check live logs, run:"
echo "  sudo journalctl -u pg-scraper.service -f"
echo "=================================================================="
