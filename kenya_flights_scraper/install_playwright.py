"""
install_playwright.py
Must sit in the same folder as app.py in your GitHub repo.
Streamlit Cloud installs the playwright Python package via requirements.txt
but never runs `playwright install chromium` — this module does that once.
"""
import subprocess
import sys
import os


def ensure_playwright_browsers():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            if os.path.exists(p.chromium.executable_path):
                return  # already installed
    except Exception:
        pass

    print("Installing Playwright Chromium...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )


ensure_playwright_browsers()
