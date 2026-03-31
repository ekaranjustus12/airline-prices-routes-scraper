#!/bin/bash
# Runs as root before the app starts — safe to apt-get here
apt-get update -qq
apt-get install -y \
  libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 \
  libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
  libgbm1 libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
  libasound2 libatspi2.0-0 libwayland-client0 fonts-liberation

# Install only the browser binary — no sudo, no --with-deps
playwright install chromium
