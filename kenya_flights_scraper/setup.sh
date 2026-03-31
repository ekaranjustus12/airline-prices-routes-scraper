"""
This module is imported at the very top of app.py to ensure
Playwright's Chromium browser binary is installed before the
scraper ever tries to launch it.

Streamlit Cloud installs Python packages from requirements.txt
but does NOT run `playwright install` automatically. Without this,
you get:
  "Executable doesn't exist at ... run `playwright install`"

The install is skipped on subsequent runs because Playwright
checks for the binary first.
"""
import subprocess
import sys
import os

def ensure_playwright_browsers():
    """Install Playwright's Chromium binary if not already present."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Just check if the executable exists — don't launch yet
            browser_path = p.chromium.executable_path
            if os.path.exists(browser_path):
                return  # already installed, nothing to do
    except Exception:
        pass  # browser not found — fall through to install

    print("Installing Playwright Chromium browser...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("Playwright Chromium installed successfully.", flush=True)
    else:
        print(f"playwright install warning: {result.stderr[:300]}", flush=True)

ensure_playwright_browsers()
