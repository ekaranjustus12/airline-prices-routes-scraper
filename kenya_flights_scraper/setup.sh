#!/usr/bin/env bash
# ── Run this ONCE on your server / local machine ──────────────────────────────
# Usage:  bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "=== Installing system dependencies for Playwright/Chromium ==="

# Detect package manager
if command -v apt-get &>/dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y \
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libxkbcommon0 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libatspi2.0-0 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxext6 \
        fonts-liberation \
        wget
    echo "=== apt-get packages installed ==="

elif command -v yum &>/dev/null; then
    # RHEL / CentOS / Amazon Linux
    sudo yum install -y \
        glib2 \
        nss \
        nspr \
        dbus-libs \
        atk \
        at-spi2-atk \
        cups-libs \
        libdrm \
        libXcomposite \
        libXdamage \
        libXfixes \
        libXrandr \
        mesa-libgbm \
        libxkbcommon \
        pango \
        cairo \
        alsa-lib \
        at-spi2-core \
        libX11 \
        libxcb \
        libXext
    echo "=== yum packages installed ==="
else
    echo "WARNING: Unknown package manager. Install Chromium system deps manually."
    echo "See: https://playwright.dev/python/docs/intro#system-requirements"
fi

echo ""
echo "=== Installing Python packages ==="
pip install --upgrade pip
pip install playwright pandas streamlit

echo ""
echo "=== Installing Playwright browsers (Chromium only) ==="
playwright install chromium

echo ""
echo "=== Installing Playwright system deps via playwright tool ==="
playwright install-deps chromium

echo ""
echo "✅  Setup complete. You can now run:  streamlit run app.py"
