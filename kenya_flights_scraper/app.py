import streamlit as st
import pandas as pd
import subprocess
import sys
import time
import os
from datetime import date, timedelta
from pathlib import Path

# ── Install Playwright browsers at startup (Streamlit Cloud) ──
@st.cache_resource
def install_playwright():
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        st.warning(f"Playwright install warning: {result.stderr[-300:]}")

install_playwright()

st.set_page_config(
    page_title="Kenya Flights",
    page_icon="✈",
    layout="wide"
)

# ── Constants ─────────────────────────────────────────
# Use the directory where app.py lives — works on Streamlit Cloud
BASE_DIR = Path(__file__).parent
CSV_FILE  = BASE_DIR / "kenya_flights_esky.csv"

ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA", "from": "NBO", "to": "MBA"},
    "Nairobi → Kisumu":  {"label": "NBO→KIS", "from": "NBO", "to": "KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL", "from": "NBO", "to": "EDL"},
}

# ── Global styles ─────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2rem 2rem 2rem; max-width: 780px; }

.page-header { margin-bottom: 1.75rem; }
.page-header h1 {
    font-size: 20px; font-weight: 600;
    display: flex; align-items: center; gap: 8px;
    color: #0f0f0f; margin: 0 0 4px 0;
}
.page-header p { font-size: 13px; color: #6b7280; margin: 0; }

.search-panel {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 1.25rem;
}

.results-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
}
.results-count { font-size: 13px; color: #6b7280; }

.flight-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 10px;
    transition: border-color 0.15s;
}
.flight-card:hover { border-color: #d1d5db; }
.flight-card.best-card { border: 1.5px solid #0F6E56; }

.card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
}
.airline-row { display: flex; align-items: center; gap: 10px; }
.airline-logo {
    width: 30px; height: 30px; border-radius: 7px;
    background: #f3f4f6; border: 1px solid #e5e7eb;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 600; color: #6b7280;
    flex-shrink: 0;
}
.airline-name { font-size: 14px; font-weight: 500; color: #111827; }
.airline-date { font-size: 12px; color: #9ca3af; margin-top: 1px; }
.best-badge {
    font-size: 11px; font-weight: 500;
    padding: 3px 9px; border-radius: 20px;
    background: #E1F5EE; color: #0F6E56;
    border: 1px solid #9FE1CB;
}

.time-row {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: 14px;
}
.time-block { min-width: 56px; }
.time-block .time { font-size: 22px; font-weight: 600; color: #111827; line-height: 1.1; }
.time-block .iata { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.route-line {
    flex: 1;
    display: flex; flex-direction: column;
    align-items: center; gap: 5px;
    padding: 0 14px;
}
.route-bar-wrap { width: 100%; display: flex; align-items: center; }
.dot { width: 5px; height: 5px; border-radius: 50%; background: #d1d5db; flex-shrink: 0; }
.bar { flex: 1; height: 1px; background: #e5e7eb; }
.route-meta { display: flex; align-items: center; gap: 8px; }
.duration { font-size: 11px; color: #9ca3af; }
.stops-pill {
    font-size: 11px; padding: 2px 8px; border-radius: 20px;
    background: #f3f4f6; border: 1px solid #e5e7eb;
    color: #6b7280;
}
.stops-pill.direct {
    background: #EAF3DE; border-color: #C0DD97; color: #3B6D11;
}

.card-bottom {
    display: flex; align-items: center;
    justify-content: space-between;
    padding-top: 12px;
    border-top: 1px solid #f3f4f6;
}
.price-kes { font-size: 18px; font-weight: 600; color: #111827; }
.price-usd { font-size: 12px; color: #9ca3af; margin-top: 1px; }
.book-btn {
    font-size: 13px; padding: 7px 16px;
    border-radius: 8px; border: 1px solid #e5e7eb;
    background: #f9fafb; color: #374151;
    cursor: pointer; font-family: inherit;
    text-decoration: none; display: inline-block;
    transition: background 0.15s;
}
.book-btn:hover { background: #f3f4f6; }
.best-card .book-btn {
    background: #E1F5EE; border-color: #9FE1CB; color: #0F6E56;
}

.refresh-row {
    display: flex; align-items: center;
    justify-content: space-between;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid #f3f4f6;
}
.last-updated { font-size: 11px; color: #d1d5db; }

.empty-state {
    text-align: center;
    padding: 3rem 1rem;
}
.empty-state h3 { font-size: 15px; font-weight: 500; color: #374151; margin-bottom: 6px; }
.empty-state p  { font-size: 13px; color: #9ca3af; }

div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }
.stSelectbox > div, .stDateInput > div { margin-bottom: 0; }
label[data-testid="stWidgetLabel"] {
    font-size: 11px !important; font-weight: 500 !important;
    color: #9ca3af !important;
    text-transform: uppercase; letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_FILE)
    df["price_kes"] = pd.to_numeric(df.get("price_kes", 0), errors="coerce").fillna(0)
    df["price_usd"] = pd.to_numeric(df.get("price_usd", 0), errors="coerce").fillna(0)
    df["stops"]     = pd.to_numeric(df.get("stops", 0),     errors="coerce").fillna(0)
    df["departure_time"] = pd.to_datetime(df["departure_time"], errors="coerce").dt.strftime("%H:%M")
    df["arrival_time"]   = pd.to_datetime(df["arrival_time"],   errors="coerce").dt.strftime("%H:%M")
    df["flight_date"] = df["flight_date"].astype(str)
    return df


# ── Helper: render one flight card ───────────────────
def render_card(row, is_best: bool, route_info: dict):
    airline   = row.get("airline", "Unknown")
    initials  = "".join(w[0] for w in airline.split()[:2]).upper()
    dep       = row.get("departure_time", "--:--")
    arr       = row.get("arrival_time",   "--:--")
    dur       = row.get("duration_mins",  "?")
    stops     = int(row.get("stops", 0))
    price_kes = int(row.get("price_kes", 0))
    price_usd = int(row.get("price_usd", 0))
    fdate     = row.get("flight_date", "")

    stops_class = "stops-pill direct" if stops == 0 else "stops-pill"
    stops_label = "Direct" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
    dur_str     = str(dur)
    dur_label   = f"{int(dur) // 60} h {int(dur) % 60} min" if dur_str.isdigit() and int(dur) >= 60 else f"{dur} min"
    card_class  = "flight-card best-card" if is_best else "flight-card"
    badge_html  = '<span class="best-badge">Best price</span>' if is_best else ""

    from_iata = route_info["from"]
    to_iata   = route_info["to"]

    st.markdown(f"""
    <div class="{card_class}">
      <div class="card-top">
        <div class="airline-row">
          <div class="airline-logo">{initials}</div>
          <div>
            <div class="airline-name">{airline}</div>
            <div class="airline-date">{fdate}</div>
          </div>
        </div>
        {badge_html}
      </div>

      <div class="time-row">
        <div class="time-block">
          <div class="time">{dep}</div>
          <div class="iata">{from_iata}</div>
        </div>
        <div class="route-line">
          <div class="route-bar-wrap">
            <div class="dot"></div>
            <div class="bar"></div>
            <div class="dot"></div>
          </div>
          <div class="route-meta">
            <span class="duration">{dur_label}</span>
            <span class="{stops_class}">{stops_label}</span>
          </div>
        </div>
        <div class="time-block" style="text-align:right">
          <div class="time">{arr}</div>
          <div class="iata">{to_iata}</div>
        </div>
      </div>

      <div class="card-bottom">
        <div>
          <div class="price-kes">KES {price_kes:,}</div>
          <div class="price-usd">≈ USD {price_usd:,}</div>
        </div>
        <a class="book-btn" href="#" onclick="return false;">View deal →</a>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Scraper trigger ───────────────────────────────────
def run_scraper():
    """Run the scraper as a subprocess and reload data."""
    import subprocess, sys
    scraper_path = BASE_DIR / "scraper.py"
    with st.spinner("Scraping latest flights... this may take 1–2 minutes."):
        result = subprocess.run(
            [sys.executable, str(scraper_path)],
            capture_output=True, text=True, timeout=180,
            cwd=str(BASE_DIR)
        )
    if result.returncode == 0:
        st.cache_data.clear()
        st.success("Flights updated!")
    else:
        st.error(f"Scraper error:\n{result.stderr[-500:]}")


# ── Page header ───────────────────────────────────────
st.markdown("""
<div class="page-header">
  <h1>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>
    </svg>
    Kenya flights
  </h1>
  <p>Live domestic fare search</p>
</div>
""", unsafe_allow_html=True)


# ── Search panel ──────────────────────────────────────
st.markdown('<div class="search-panel">', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    selected_route = st.selectbox("Route", list(ROUTES.keys()), label_visibility="visible")
with col2:
    selected_date = st.date_input(
        "Departure date",
        value=date.today(),
        min_value=date.today(),
        max_value=date.today() + timedelta(days=30),
        label_visibility="visible"
    )

col3, col4 = st.columns([3, 1])
with col3:
    auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=False)
with col4:
    if st.button("🔄 Fetch flights", use_container_width=True):
        run_scraper()

last_updated = time.strftime("%H:%M:%S")
st.markdown(f"""
<div class="refresh-row">
  <span style="font-size:13px;color:#6b7280;">
    {'🟢 Auto-refresh on' if auto_refresh else '⚪ Auto-refresh off'}
  </span>
  <span class="last-updated">Updated {last_updated}</span>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# ── Load + filter ─────────────────────────────────────
df = load_data()
route_info  = ROUTES[selected_route]
route_label = route_info["label"]
date_str    = str(selected_date)

if not df.empty:
    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] >= date_str)
    ].sort_values("price_kes").reset_index(drop=True)
else:
    filtered = pd.DataFrame()


# ── Results ───────────────────────────────────────────
if filtered.empty:
    st.markdown("""
    <div class="empty-state">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none"
           stroke="#9ca3af" stroke-width="1.5" stroke-linecap="round"
           stroke-linejoin="round" style="margin:0 auto 12px;display:block">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <h3>No flights found</h3>
      <p>Click "Fetch flights" to scrape latest fares, or try a different route/date.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    cheapest = filtered["price_kes"].min()
    st.markdown(f"""
    <div class="results-header">
      <span class="results-count">{len(filtered)} flight{'s' if len(filtered) != 1 else ''} found</span>
      <span style="font-size:12px;color:#9ca3af;">Sorted by price</span>
    </div>
    """, unsafe_allow_html=True)

    for _, row in filtered.iterrows():
        render_card(row, row["price_kes"] == cheapest, route_info)


# ── Auto-refresh logic ────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
