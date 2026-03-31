import asyncio
import re
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

# ── Config ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "kenya_flights_esky.csv"

USD_TO_KES = 130
MAX_DAYS = 7
DEBUG = False

SEARCHES = [
    {"from_code": "NBO", "to_code": "MBA", "label": "NBO→MBA"},
    {"from_code": "NBO", "to_code": "KIS", "label": "NBO→KIS"},
    {"from_code": "NBO", "to_code": "EDL", "label": "NBO→EDL"},
]

# ── URL builder ───────────────────────────────────────
def search_url(search, flight_date):
    return (
        f"https://www.esky.co.ke/flights/search/mp/{search['from_code']}"
        f"/ap/{search['to_code']}"
        f"?departureDate={flight_date}"
        f"&sc=economy&pa=1&py=0&pc=0&pi=0&flexDatesOffset=0"
    )

# ── Stealth JS ────────────────────────────────────────
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-KE','en'] });
"""

# ── Warm-up ───────────────────────────────────────────
async def warm_up(context):
    page = await context.new_page()
    try:
        await page.goto("https://www.esky.co.ke", timeout=30000)
        await page.wait_for_timeout(3000)
    except:
        pass
    await page.close()

# ── HTML fallback (simplified + reliable) ─────────────
async def scrape_html(page, search, flight_date):
    flights = []
    today = str(date.today())

    await page.wait_for_timeout(6000)

    text = await page.content()

    prices = re.findall(r'US\$\s*([\d,]+(?:\.\d+)?)', text)
    times = re.findall(r'\b([0-2]?\d:[0-5]\d)\b', text)

    for i, p in enumerate(prices[:10]):  # limit to avoid noise
        price_usd = float(p.replace(",", ""))

        flights.append({
            "date_scraped": today,
            "flight_date": flight_date,
            "route": search["label"],
            "departure_time": times[i*2] if len(times) > i*2 else "",
            "arrival_time": times[i*2+1] if len(times) > i*2+1 else "",
            "duration_mins": "",
            "airline": "Unknown",
            "stops": 0,
            "price_usd": price_usd,
            "price_kes": int(price_usd * USD_TO_KES),
        })

    return flights

# ── Fetch one date ────────────────────────────────────
async def fetch_date(context, search, flight_date):
    page = await context.new_page()
    await context.add_init_script(STEALTH_JS)

    url = search_url(search, flight_date)

    try:
        await page.goto(url, timeout=60000)
    except Exception as e:
        if DEBUG:
            print("Navigation error:", e)

    flights = await scrape_html(page, search, flight_date)

    await page.close()
    return flights

# ── Route loop ────────────────────────────────────────
async def fetch_route(context, search):
    for offset in range(MAX_DAYS):
        flight_date = (date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")

        flights = await fetch_date(context, search, flight_date)

        if flights:
            return flights

        await asyncio.sleep(2)

    return []

# ── MAIN ENTRY (IMPORTANT FIX) ────────────────────────
async def main():
    all_flights = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0",
            locale="en-KE"
        )

        await warm_up(context)

        for search in SEARCHES:
            flights = await fetch_route(context, search)
            all_flights.extend(flights)
            await asyncio.sleep(3)

        await browser.close()

    df = pd.DataFrame(all_flights)

    if not df.empty:
        df.to_csv(CSV_FILE, index=False)
        print(f"Saved {len(df)} rows")
    else:
        print("No data scraped — keeping old file")

# 🔑 REQUIRED for Streamlit subprocess
if __name__ == "__main__":
    asyncio.run(main())
