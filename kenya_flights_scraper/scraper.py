"""
scraper.py  —  Flight scraper using httpx (no browser / no Playwright needed)
Calls eSky's internal JSON API directly, with session cookie warm-up.
Run directly:  python scraper.py
Called by app.py via subprocess when user clicks "Fetch flights".
"""

import sys
import time
import random
import re
import json
import httpx
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CSV_FILE   = BASE_DIR / "kenya_flights_esky.csv"
USD_TO_KES = 130
MAX_DAYS   = 7
DEBUG      = False

SEARCHES = [
    {"from_code": "NAIR", "to_code": "MBA", "label": "NBO→MBA"},
    {"from_code": "NAIR", "to_code": "KIS", "label": "NBO→KIS"},
    {"from_code": "NAIR", "to_code": "EDL", "label": "NBO→EDL"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-KE,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.esky.co.ke/",
    "Origin":          "https://www.esky.co.ke",
    "Connection":      "keep-alive",
}


# ── URLs to attempt ───────────────────────────────────
def all_urls(search: dict, flight_date: str) -> list:
    f, t, d = search["from_code"], search["to_code"], flight_date
    return [
        # JSON API variants
        (f"https://www.esky.co.ke/api/v1/flights/search"
         f"?from={f}&to={t}&departureDate={d}"
         f"&adults=1&children=0&infants=0&cabinClass=economy&currency=USD&locale=en-KE"),
        (f"https://www.esky.co.ke/flights/api/search"
         f"?from={f}&to={t}&date={d}&adults=1&cabin=economy"),
        (f"https://www.esky.co.ke/api/flights"
         f"?originLocationCode={f}&destinationLocationCode={t}"
         f"&departureDate={d}&adults=1&travelClass=ECONOMY&currencyCode=USD&max=20"),
        (f"https://www.esky.co.ke/proxy/flights/offers/search"
         f"?originDestinations={f}-{t}-{d}&travelers=1ADT&sources=GDS&currency=USD"),
        # HTML page (contains embedded JSON state)
        (f"https://www.esky.co.ke/flights/search/mp/{f}/ap/{t}"
         f"?departureDate={d}&sc=economy&pa=1&py=0&pc=0&pi=0&flexDatesOffset=0"),
    ]


# ── JSON response parser ──────────────────────────────
def parse_response(data: dict, search: dict, flight_date: str) -> list:
    flights   = []
    today_str = str(date.today())
    carriers  = data.get("dictionaries", {}).get("carriers", {})

    rows = []
    for k in ["blocks", "itineraries", "results", "offers", "flights",
              "items", "searchResults", "flightOffers", "propositions",
              "data", "content", "flightOptions"]:
        val = data.get(k)
        if isinstance(val, list) and val:
            rows = val
            if DEBUG:
                print(f"  key='{k}'  {len(rows)} items")
            break

    for block in rows:
        if not isinstance(block, dict):
            continue
        try:
            pd_ = block.get("priceDetails") or block.get("price") or {}
            if isinstance(pd_, dict):
                price_usd = (pd_.get("grandTotal") or pd_.get("total")
                             or pd_.get("amount") or pd_.get("value"))
            else:
                price_usd = float(pd_) if pd_ else None
            price_usd = price_usd or block.get("totalPrice") or block.get("fare")
            if price_usd is None:
                continue
            price_usd = float(price_usd)
            price_kes = int(price_usd * USD_TO_KES)

            itineraries = (block.get("legGroups") or block.get("legs")
                           or block.get("itineraries") or [block])

            for group in itineraries:
                codes   = group.get("airlineCodes", [])
                carrier = group.get("carrierCode", "")
                airline = (
                    " + ".join(carriers.get(c, {}).get("name", c)
                               if isinstance(carriers.get(c), dict)
                               else carriers.get(c, c) for c in codes)
                    or carriers.get(carrier, {}).get("name", carrier)
                    or group.get("airline", "Unknown")
                )
                segments = group.get("legs") or group.get("segments") or [group]
                stops    = group.get("transferCount", max(0, len(segments) - 1))
                first, last = segments[0], segments[-1]

                dep = (first.get("from", {}).get("time")
                       or first.get("from", {}).get("dateTime")
                       or first.get("departure", {}).get("at", ""))
                arr = (last.get("to", {}).get("time")
                       or last.get("to", {}).get("dateTime")
                       or last.get("arrival", {}).get("at", ""))
                dur = group.get("duration") or group.get("duration_mins", "")

                flights.append({
                    "date_scraped":   today_str,
                    "flight_date":    flight_date,
                    "route":          search["label"],
                    "departure_time": dep,
                    "arrival_time":   arr,
                    "duration_mins":  dur,
                    "airline":        airline,
                    "stops":          stops,
                    "price_usd":      round(price_usd, 2),
                    "price_kes":      price_kes,
                })
        except Exception as e:
            if DEBUG:
                print(f"  [block err] {e}")
    return flights


# ── HTML embedded-JSON extractor ──────────────────────
def parse_html(html: str, search: dict, flight_date: str) -> list:
    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;?\s*</script>',
        r'window\.__data\s*=\s*(\{.+?\})\s*;',
        r'"flightOffers"\s*:\s*(\[.+?\])',
        r'"results"\s*:\s*(\[.+?\])',
        r'"blocks"\s*:\s*(\[.+?\])',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if not m:
            continue
        try:
            blob = json.loads(m.group(1))
            if isinstance(blob, list):
                blob = {"results": blob}
            result = parse_response(blob, search, flight_date)
            if result:
                return result
        except Exception:
            continue

    # Last-resort: regex visible prices
    flights   = []
    today_str = str(date.today())
    seen      = set()
    known_airlines = ["Kenya Airways", "Jambojet", "Skyward Express",
                      "FlySax", "Safarilink", "AirKenya", "African Express"]

    for m in re.finditer(r'US\$\s*([\d,]+(?:\.\d+)?)', html):
        price_usd = float(m.group(1).replace(",", ""))
        key = round(price_usd)
        if key in seen:
            continue
        seen.add(key)
        ctx     = html[max(0, m.start()-300): m.end()+200]
        times   = re.findall(r'\b([0-2]?\d:[0-5]\d)\b', ctx)
        airline = next((a for a in known_airlines if a.lower() in ctx.lower()), "Unknown")
        dur_m   = re.search(r'(\d+)\s*h\s*(\d+)\s*m', ctx, re.I)
        dur     = int(dur_m.group(1))*60 + int(dur_m.group(2)) if dur_m else ""
        flights.append({
            "date_scraped":   today_str,
            "flight_date":    flight_date,
            "route":          search["label"],
            "departure_time": times[0] if times else "",
            "arrival_time":   times[1] if len(times) > 1 else "",
            "duration_mins":  dur,
            "airline":        airline,
            "stops":          0,
            "price_usd":      round(price_usd, 2),
            "price_kes":      int(price_usd * USD_TO_KES),
        })
    return flights


# ── Fetch one date ────────────────────────────────────
def fetch_for_date(client: httpx.Client, search: dict, flight_date: str) -> list:
    for url in all_urls(search, flight_date):
        try:
            if DEBUG:
                print(f"  GET {url[:100]}")
            resp = client.get(url, timeout=30)
            if DEBUG:
                print(f"  -> {resp.status_code}  ct={resp.headers.get('content-type','')[:60]}")
            if resp.status_code != 200:
                continue
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                data    = resp.json()
                if isinstance(data, list):
                    data = {"results": data}
                flights = parse_response(data, search, flight_date)
            else:
                flights = parse_html(resp.text, search, flight_date)
            if flights:
                print(f"  Found {len(flights)} flights")
                return flights
        except Exception as e:
            if DEBUG:
                print(f"  [err] {e}")
        time.sleep(random.uniform(1.5, 3.0))
    return []


# ── Route loop ────────────────────────────────────────
def fetch_route(client: httpx.Client, search: dict) -> list:
    print(f"\n{'='*56}\n  Route: {search['label']}\n{'='*56}")
    for offset in range(MAX_DAYS + 1):
        flight_date = (date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")
        print(f"\n  {flight_date}  ({'today' if offset==0 else f'today+{offset}'})")
        flights = fetch_for_date(client, search, flight_date)
        if flights:
            return flights
        print(f"  Nothing — trying next day...")
        time.sleep(random.uniform(2, 4))
    print(f"  No data for {search['label']} over {MAX_DAYS+1} days")
    return []


# ── Main ──────────────────────────────────────────────
def run():
    all_flights = []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        print("Warming up session...")
        try:
            client.get("https://www.esky.co.ke", timeout=15)
            time.sleep(2)
            print("  Session ready")
        except Exception as e:
            print(f"  Warm-up warning: {e}")

        for search in SEARCHES:
            flights = fetch_route(client, search)
            all_flights.extend(flights)
            time.sleep(random.uniform(3, 6))

    df = pd.DataFrame(all_flights)
    if not df.empty:
        df.to_csv(CSV_FILE, index=False)
        print(f"\nSaved {len(df)} rows -> {CSV_FILE}")
        cols = ["route", "flight_date", "airline", "departure_time",
                "arrival_time", "stops", "price_kes"]
        print(df.sort_values(["route", "price_kes"])[
            [c for c in cols if c in df.columns]].to_string(index=False))
    else:
        print("\nNo flights scraped.")
        sys.exit(1)


if __name__ == "__main__":
    run()
