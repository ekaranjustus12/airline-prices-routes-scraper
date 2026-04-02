"""
scraper_github.py
─────────────────
Standalone version of the scraper for GitHub Actions.
No Colab, no Google Drive — reads/writes CSV relative to this file.
Run via: python kenya_flights_scraper/scraper_github.py
"""

import asyncio
import re
import sys
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CSV_FILE   = BASE_DIR / "kenya_flights_esky.csv"

USD_TO_KES       = 130
MAX_DAYS         = 7
SCRAPE_ALL_DATES = True
DEBUG            = False

ALL_SEARCHES = [
    {"from_code": "NAIR", "to_code": "MBA", "label": "NBO→MBA"},
    {"from_code": "NAIR", "to_code": "KIS", "label": "NBO→KIS"},
    {"from_code": "NAIR", "to_code": "EDL", "label": "NBO→EDL"},
]

STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-KE', 'en'] });
"""

def search_url(search, flight_date):
    return (
        f"https://www.esky.co.ke/flights/search/mp/{search['from_code']}"
        f"/ap/{search['to_code']}"
        f"?departureDate={flight_date}"
        f"&sc=economy&pa=1&py=0&pc=0&pi=0&flexDatesOffset=0"
    )

async def warm_up(context):
    page = await context.new_page()
    try:
        await page.goto("https://www.esky.co.ke", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)
        print("  Session ready")
    except Exception as e:
        print(f"  Warm-up warning: {e}")
    finally:
        await page.close()

async def fetch_for_date(context, search, flight_date):
    captured = []
    page = await context.new_page()

    async def on_response(response):
        if response.status != 200:
            return
        if "application/json" not in response.headers.get("content-type", ""):
            return
        try:
            data = await response.json()
            if not isinstance(data, dict):
                return
            for k in ["blocks","itineraries","results","offers","flights",
                      "items","searchResults","flightOffers","propositions","data"]:
                if k in data and isinstance(data[k], list) and data[k]:
                    print(f"  JSON key='{k}' ({len(data[k])} items)")
                    captured.append({"data": data, "key": k})
                    break
        except Exception:
            pass

    page.on("response", on_response)
    print(f"  GET {search_url(search, flight_date)}")

    try:
        await page.goto(search_url(search, flight_date),
                        wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"  Nav error: {e}")

    for i in range(23):
        if captured:
            print(f"  JSON arrived ~{(i+1)*2}s")
            break
        await page.wait_for_timeout(2000)
    else:
        print("  No JSON — trying HTML fallback...")

    flights = parse_json(captured, search, flight_date) if captured else []
    if not flights:
        flights = await scrape_html(page, search, flight_date)

    await page.close()
    return flights

def parse_json(captured, search, flight_date):
    flights   = []
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    for cap in captured:
        data     = cap["data"]
        key      = cap["key"]
        carriers = data.get("dictionaries", {}).get("carriers", {})
        for block in data.get(key, []):
            try:
                pd_ = block.get("priceDetails") or block.get("price") or {}
                price_usd = (pd_.get("amount") or pd_.get("total") or pd_.get("value")
                             if isinstance(pd_, dict) else float(pd_) if pd_ else None)
                price_usd = price_usd or block.get("totalPrice") or block.get("fare")
                if price_usd is None:
                    continue
                price_usd = float(price_usd)
                for group in (block.get("legGroups") or block.get("legs") or []):
                    codes   = group.get("airlineCodes", [])
                    airline = " + ".join(
                        carriers.get(c, {}).get("name", c)
                        if isinstance(carriers.get(c), dict) else carriers.get(c, c)
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
                            "price_kes":      int(price_usd * USD_TO_KES),
                            "source":         "api",
                        })
            except Exception as e:
                if DEBUG: print(f"  [block err] {e}")
    return flights

async def scrape_html(page, search, flight_date):
    flights   = []
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    await page.wait_for_timeout(6000)

    cards = []
    for sel in ["[data-testid*='flight']","[class*='FlightResult']",
                "[class*='result-item']","[class*='offer-item']",
                "[class*='result']:not(body):not(html)"]:
        cards = await page.query_selector_all(sel)
        if cards:
            print(f"  HTML: {len(cards)} cards via '{sel}'")
            break

    known = ["Kenya Airways","KQ","Jambojet","Skyward Express",
             "FlySax","Safarilink","AirKenya","African Express"]
    seen  = set()

    for card in cards:
        try:
            text = (await card.inner_text()).strip()
            if len(text) < 10:
                continue
            price_usd = None
            m = re.search(r'KES\s*([\d,]+)', text)
            if m:
                price_usd = float(m.group(1).replace(",","")) / USD_TO_KES
            else:
                m = re.search(r'US\$\s*([\d,]+(?:\.\d+)?)', text)
                if m:
                    price_usd = float(m.group(1).replace(",",""))
            if price_usd is None or price_usd * USD_TO_KES < 500:
                continue
            sig = (round(price_usd,0), text[:40])
            if sig in seen: continue
            seen.add(sig)
            times   = re.findall(r'\b([0-1]\d:[0-5]\d|2[0-3]:[0-5]\d)\b', text)
            dur     = ""
            m = re.search(r'(\d+)\s*h\s*(\d+)\s*m', text, re.I)
            if m: dur = int(m.group(1))*60 + int(m.group(2))
            airline = next((a for a in known if a.lower() in text.lower()), "Unknown")
            stops   = 0
            m = re.search(r'(\d+)\s+stop', text, re.I)
            if m: stops = int(m.group(1))
            flights.append({
                "date_scraped":   today_str,
                "flight_date":    flight_date,
                "route":          search["label"],
                "departure_time": times[0] if times else "",
                "arrival_time":   times[1] if len(times)>1 else "",
                "duration_mins":  dur,
                "airline":        airline,
                "stops":          stops,
                "price_usd":      round(price_usd,2),
                "price_kes":      int(price_usd*USD_TO_KES),
                "source":         "html_scrape",
            })
        except Exception:
            continue
    return flights

async def fetch_route(context, search):
    print(f"\n{'='*54}\n  Route: {search['label']}\n{'='*54}")
    all_flights = []
    for offset in range(MAX_DAYS + 1):
        flight_date = (date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")
        print(f"\n  {flight_date}")
        flights = await fetch_for_date(context, search, flight_date)
        if flights:
            print(f"  {len(flights)} flight(s) found")
            all_flights.extend(flights)
            if not SCRAPE_ALL_DATES:
                return all_flights
        else:
            print("  Nothing found")
        await asyncio.sleep(3)
    return all_flights

async def main():
    all_flights = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 800},
            locale="en-KE",
        )
        await context.add_init_script(STEALTH_JS)
        await warm_up(context)

        for search in ALL_SEARCHES:
            flights = await fetch_route(context, search)
            all_flights.extend(flights)
            await asyncio.sleep(8)

        await browser.close()

    if not all_flights:
        print("No flights scraped.")
        sys.exit(0)   # exit 0 so GitHub Actions doesn't mark it failed

    df = pd.DataFrame(all_flights)

    # Merge with existing CSV — don't overwrite historical data
    if CSV_FILE.exists():
        old = pd.read_csv(CSV_FILE)
        # Drop rows older than 30 days to keep the file lean
        old["flight_date"] = pd.to_datetime(old["flight_date"], errors="coerce")
        cutoff = pd.Timestamp(date.today() - timedelta(days=30))
        old = old[old["flight_date"] >= cutoff]
        old["flight_date"] = old["flight_date"].dt.strftime("%Y-%m-%d")
        df = pd.concat([old, df], ignore_index=True).drop_duplicates(
            subset=["route", "flight_date", "departure_time", "price_kes"]
        )

    df.to_csv(CSV_FILE, index=False)
    print(f"\nSaved {len(df)} rows → {CSV_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
