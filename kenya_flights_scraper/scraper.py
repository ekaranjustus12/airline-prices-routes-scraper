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
DEBUG = True  # set False in production

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

# ── Warm-up (stealth applied at context level) ────────
async def warm_up(context):
    page = await context.new_page()
    try:
        await page.goto("https://www.esky.co.ke", timeout=30000)
        await page.wait_for_timeout(3000)
    except Exception as e:
        if DEBUG:
            print("Warm-up error:", e)
    await page.close()

# ── Parse flight cards from rendered HTML ─────────────
async def scrape_html(page, search, flight_date):
    """
    Wait for flight results to render, then parse structured card data.
    Falls back to broad regex only if no structured data found.
    """
    flights = []
    today = str(date.today())

    # Wait for results to load (adjust selector if esky changes their DOM)
    try:
        await page.wait_for_selector("[class*='result'], [class*='flight'], [class*='offer']",
                                     timeout=15000)
    except Exception:
        pass  # fall through to regex

    await page.wait_for_timeout(3000)

    # ── Try structured parsing first ──────────────────
    # esky.co.ke uses KES prices directly; look for numeric KES amounts
    content = await page.content()

    if DEBUG:
        print(f"Page content length: {len(content)} chars")

    # Match KES prices like: KES 12,345 or KES12345 or 12,345 KES
    kes_prices = re.findall(r'(?:KES\s*)([\d,]+)', content)
    # Also match plain large integers that look like fares (4-6 digits)
    # only as fallback — esky KE shows KES explicitly
    if not kes_prices:
        # fallback: USD prices converted
        usd_prices = re.findall(r'US\$\s*([\d,]+(?:\.\d+)?)', content)
        prices_kes = [int(float(p.replace(",", "")) * USD_TO_KES) for p in usd_prices]
    else:
        prices_kes = [int(p.replace(",", "")) for p in kes_prices]

    # Match times — only accept HH:MM patterns inside likely flight result blocks
    # Restrict to reasonable flight times (04:00–23:59) to reduce noise
    raw_times = re.findall(r'\b([0-1]\d:[0-5]\d|2[0-3]:[0-5]\d)\b', content)

    # De-duplicate consecutive identical times (nav bars repeat the same time)
    times = []
    for t in raw_times:
        if not times or t != times[-1]:
            times.append(t)

    if DEBUG:
        print(f"Found {len(prices_kes)} prices, {len(times)} times")

    for i, price_kes in enumerate(prices_kes[:20]):  # cap at 20 results
        # Skip implausibly low prices (likely not fares)
        if price_kes < 500:
            continue

        dep = times[i * 2] if len(times) > i * 2 else ""
        arr = times[i * 2 + 1] if len(times) > i * 2 + 1 else ""

        flights.append({
            "date_scraped": today,
            "flight_date": flight_date,
            "route": search["label"],
            "departure_time": dep,
            "arrival_time": arr,
            "duration_mins": "",
            "airline": "Unknown",
            "stops": 0,
            "price_usd": round(price_kes / USD_TO_KES, 2),
            "price_kes": price_kes,
        })

    return flights

# ── Fetch one specific date ────────────────────────────
async def fetch_date(context, search, flight_date):
    page = await context.new_page()
    url = search_url(search, flight_date)

    if DEBUG:
        print(f"Fetching: {url}")

    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        if DEBUG:
            print("Navigation error:", e)

    flights = await scrape_html(page, search, flight_date)
    await page.close()
    return flights

# ── Route loop — collect ALL dates, don't stop early ──
async def fetch_route(context, search):
    """
    Collect flights for every date in the window.
    Previously returned on first hit — now accumulates all results.
    """
    all_flights = []

    for offset in range(MAX_DAYS):
        flight_date = (date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")
        flights = await fetch_date(context, search, flight_date)

        if DEBUG:
            print(f"  {search['label']} {flight_date}: {len(flights)} flights")

        all_flights.extend(flights)
        await asyncio.sleep(2)

    return all_flights

# ── Main ──────────────────────────────────────────────
async def main():
    all_flights = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        # FIX: add_init_script at CONTEXT level so stealth JS runs
        # before every page navigation — not after new_page()
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-KE",
            viewport={"width": 1280, "height": 800},
        )
        await context.add_init_script(STEALTH_JS)  # applied to ALL pages in context

        await warm_up(context)

        for search in SEARCHES:
            print(f"Scraping route: {search['label']}")
            flights = await fetch_route(context, search)
            all_flights.extend(flights)
            await asyncio.sleep(3)

        await browser.close()

    df = pd.DataFrame(all_flights)

    if not df.empty:
        df.to_csv(CSV_FILE, index=False)
        print(f"Saved {len(df)} rows to {CSV_FILE}")
    else:
        print("No data scraped — keeping old file if it exists")

if __name__ == "__main__":
    asyncio.run(main())
