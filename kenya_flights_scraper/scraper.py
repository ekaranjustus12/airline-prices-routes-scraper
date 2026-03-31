"""
scraper.py  –  Kenya domestic flight scraper (eSky)
────────────────────────────────────────────────────
Run directly:          python scraper.py
From app.py sidebar:   env vars SCRAPE_ROUTE / SCRAPE_DATE are respected.

System prerequisite:   bash setup.sh   (installs Chromium + system libs)
"""

import asyncio
import os
import re
import sys
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CSV_FILE    = BASE_DIR / "kenya_flights_esky.csv"

USD_TO_KES  = 130
MAX_DAYS    = 7
DEBUG       = True   # set False to silence verbose output

# Optional env-var overrides (set by app.py sidebar scrape button)
ENV_ROUTE   = os.environ.get("SCRAPE_ROUTE")   # e.g. "NBO→MBA"
ENV_DATE    = os.environ.get("SCRAPE_DATE")     # e.g. "2026-04-01"

ALL_SEARCHES = [
    {"from_code": "NAIR", "to_code": "MBA", "label": "NBO→MBA"},
    {"from_code": "NAIR", "to_code": "KIS", "label": "NBO→KIS"},
    {"from_code": "NAIR", "to_code": "EDL", "label": "NBO→EDL"},
]

# Filter to a single route if requested by the app sidebar
SEARCHES = (
    [s for s in ALL_SEARCHES if s["label"] == ENV_ROUTE]
    if ENV_ROUTE else ALL_SEARCHES
)

# ── URL builder ────────────────────────────────────────────────────────────────
def search_url(search: dict, flight_date: str) -> str:
    """
    mp = metro/city point   ap = airport point
    pa=1  → 1 adult   sc=economy
    """
    return (
        f"https://www.esky.co.ke/flights/search/mp/{search['from_code']}"
        f"/ap/{search['to_code']}"
        f"?departureDate={flight_date}"
        f"&sc=economy&pa=1&py=0&pc=0&pi=0&flexDatesOffset=0"
    )

# ── Stealth JS ─────────────────────────────────────────────────────────────────
STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-KE', 'en'] });
"""

# ── Warm-up ────────────────────────────────────────────────────────────────────
async def warm_up_session(context):
    """Visit the homepage first to pick up session cookies."""
    print("Warming up session...")
    page = await context.new_page()
    try:
        await page.goto("https://www.esky.co.ke",
                        wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        print("  Session ready")
    except Exception as e:
        print(f"  Warm-up warning (non-fatal): {e}")
    finally:
        await page.close()

# ── JSON response interceptor ─────────────────────────────────────────────────
async def fetch_for_date(context, search: dict, flight_date: str) -> list:
    captured = []
    page     = await context.new_page()
    # NOTE: add_init_script is called at CONTEXT level in main() so stealth
    # JS is injected before every navigation — not here after new_page().

    async def on_response(response):
        if response.status != 200:
            return
        ct = response.headers.get("content-type", "")
        if "application/json" not in ct:
            return
        try:
            data = await response.json()
            if not isinstance(data, dict) or not data:
                return
            if DEBUG:
                print(f"  [API] {response.url[:90]}")
                print(f"        keys: {list(data.keys())[:8]}")
            for k in ["blocks", "itineraries", "results", "offers", "flights",
                      "items", "searchResults", "flightOffers", "propositions", "data"]:
                if k in data and isinstance(data[k], list) and data[k]:
                    print(f"  JSON key='{k}' ({len(data[k])} items)")
                    captured.append({"data": data, "key": k})
                    break
        except Exception as e:
            if DEBUG:
                print(f"  [json err] {e}")

    page.on("response", on_response)

    url = search_url(search, flight_date)
    print(f"GET {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"  Nav error: {e}")

    # Poll up to 45 s for XHR data
    for i in range(23):
        if captured:
            print(f"  JSON arrived ~{(i + 1) * 2}s")
            break
        await page.wait_for_timeout(2000)
    else:
        print("  No JSON after 46 s — trying HTML fallback...")

    flights = []
    if captured:
        flights = parse_json(captured, search, flight_date)

    if not flights:
        flights = await scrape_html(page, search, flight_date)

    if not flights and DEBUG:
        print(f"  Final URL : {page.url}")
        print(f"  Title     : {await page.title()}")
        html = await page.content()
        print(f"  HTML[:800]: {html[:800]}")

    await page.close()
    return flights

# ── JSON parser ────────────────────────────────────────────────────────────────
def parse_json(captured: list, search: dict, flight_date: str) -> list:
    flights   = []
    today_str = str(date.today())

    for cap in captured:
        data     = cap["data"]
        key      = cap["key"]
        carriers = data.get("dictionaries", {}).get("carriers", {})

        for block in data.get(key, []):
            try:
                pd_ = block.get("priceDetails") or block.get("price") or {}
                if isinstance(pd_, dict):
                    price_usd = (pd_.get("amount") or pd_.get("total")
                                 or pd_.get("value"))
                else:
                    price_usd = float(pd_) if pd_ else None
                price_usd = (price_usd or block.get("totalPrice")
                             or block.get("fare"))
                if price_usd is None:
                    continue
                price_usd = float(price_usd)
                price_kes = int(price_usd * USD_TO_KES)

                for group in (block.get("legGroups") or block.get("legs") or []):
                    codes   = group.get("airlineCodes", [])
                    airline = " + ".join(
                        carriers.get(c, {}).get("name", c)
                        if isinstance(carriers.get(c), dict)
                        else carriers.get(c, c)
                        for c in codes
                    ) or group.get("airline", "Unknown")

                    for leg in group.get("legs", [group]):
                        dep = leg.get("from", {})
                        arr = leg.get("to",   {})
                        flights.append({
                            "date_scraped":   today_str,
                            "flight_date":    flight_date,
                            "route":          search["label"],
                            "departure_time": dep.get("time") or dep.get("dateTime", ""),
                            "arrival_time":   arr.get("time") or arr.get("dateTime", ""),
                            "duration_mins":  leg.get("duration") or group.get("duration", ""),
                            "airline":        airline,
                            "stops":          group.get("transferCount", 0),
                            "price_usd":      price_usd,
                            "price_kes":      price_kes,
                            "source":         "api",
                        })
            except Exception as e:
                if DEBUG:
                    print(f"  [block err] {e}")
    return flights

# ── HTML fallback ──────────────────────────────────────────────────────────────
async def scrape_html(page, search: dict, flight_date: str) -> list:
    flights   = []
    today_str = str(date.today())

    await page.wait_for_timeout(6000)

    selectors = [
        "[data-testid*='flight']",
        "[class*='SearchResults']",
        "[class*='FlightResult']",
        "[class*='result-item']",
        "[class*='offer-item']",
        "[class*='flight-item']",
        "[class*='result']:not(body):not(html)",
    ]
    cards = []
    for sel in selectors:
        cards = await page.query_selector_all(sel)
        if cards:
            print(f"  HTML: {len(cards)} cards via '{sel}'")
            break
    else:
        print("  HTML: no cards matched any selector")
        return flights

    known_airlines = [
        "Kenya Airways", "KQ", "Jambojet", "Skyward Express",
        "FlySax", "Safarilink", "AirKenya", "African Express",
    ]
    seen = set()

    for card in cards:
        try:
            text = (await card.inner_text()).strip()
            if len(text) < 10:
                continue

            # Price — prefer KES, fall back to USD
            price_usd = None
            m = re.search(r'KES\s*([\d,]+)', text)
            if m:
                price_usd = float(m.group(1).replace(",", "")) / USD_TO_KES
            else:
                m = re.search(r'US\$\s*([\d,]+(?:\.\d+)?)', text)
                if m:
                    price_usd = float(m.group(1).replace(",", ""))
            if price_usd is None:
                continue

            sig = (round(price_usd, 0), text[:40])
            if sig in seen:
                continue
            seen.add(sig)

            # Times
            times = re.findall(r'\b([0-1]\d:[0-5]\d|2[0-3]:[0-5]\d)\b', text)

            # Duration
            dur = ""
            m = re.search(r'(\d+)\s*h\s*(\d+)\s*m', text, re.I)
            if m:
                dur = int(m.group(1)) * 60 + int(m.group(2))

            # Airline
            airline = next(
                (a for a in known_airlines if a.lower() in text.lower()),
                "Unknown"
            )

            # Stops
            stops = 0
            m = re.search(r'(\d+)\s+stop', text, re.I)
            if m:
                stops = int(m.group(1))
            elif re.search(r'\bdirect\b|\bnonstop\b', text, re.I):
                stops = 0

            flights.append({
                "date_scraped":   today_str,
                "flight_date":    flight_date,
                "route":          search["label"],
                "departure_time": times[0] if len(times) > 0 else "",
                "arrival_time":   times[1] if len(times) > 1 else "",
                "duration_mins":  dur,
                "airline":        airline,
                "stops":          stops,
                "price_usd":      round(price_usd, 2),
                "price_kes":      int(price_usd * USD_TO_KES),
                "source":         "html_scrape",
            })
        except Exception:
            continue

    return flights

# ── Date-loop with fallback ────────────────────────────────────────────────────
async def fetch_route_with_fallback(context, search: dict) -> list:
    """
    If ENV_DATE is set (from sidebar), try that date only.
    Otherwise walk today → today+MAX_DAYS and return at the first hit.
    """
    print(f"\n{'='*56}")
    print(f"  Route: {search['label']}")
    print(f"{'='*56}")

    if ENV_DATE:
        dates_to_try = [ENV_DATE]
    else:
        dates_to_try = [
            (date.today() + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(MAX_DAYS + 1)
        ]

    for flight_date in dates_to_try:
        print(f"\n  Trying {flight_date}...")
        flights = await fetch_for_date(context, search, flight_date)
        if flights:
            print(f"  {len(flights)} flight(s) found for {flight_date}")
            return flights
        print(f"  Nothing for {flight_date} — trying next day...")
        await asyncio.sleep(3)

    print(f"  No data for {search['label']} in window searched")
    return []

# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    all_flights = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-KE",
        )

        # Stealth JS applied at CONTEXT level — runs before every page navigation
        await context.add_init_script(STEALTH_JS)

        await warm_up_session(context)

        print(f"\n{len(SEARCHES)} route(s) | up to {MAX_DAYS} days ahead\n")

        for search in SEARCHES:
            flights = await fetch_route_with_fallback(context, search)
            all_flights.extend(flights)
            await asyncio.sleep(8)

        await browser.close()

    df = pd.DataFrame(all_flights)

    if not df.empty:
        # Merge with existing CSV so old dates aren't wiped on each run
        if CSV_FILE.exists():
            old = pd.read_csv(CSV_FILE)
            df  = pd.concat([old, df], ignore_index=True).drop_duplicates(
                subset=["route", "flight_date", "departure_time", "price_kes"]
            )
        df.to_csv(CSV_FILE, index=False)
        print(f"\nSaved {len(df)} rows → {CSV_FILE}\n")

        cols = ["route", "flight_date", "airline",
                "departure_time", "arrival_time", "stops", "price_kes", "source"]
        print(
            df.sort_values(["route", "price_kes"])[
                [c for c in cols if c in df.columns]
            ].to_string(index=False)
        )
    else:
        print("\nNo flights scraped — existing CSV unchanged.")
        sys.exit(1)   # non-zero so app.py can detect failure


if __name__ == "__main__":
    asyncio.run(main())
