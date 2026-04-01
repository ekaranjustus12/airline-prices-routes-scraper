import install_playwright  # noqa: F401  — must be first line

import streamlit as st
import pandas as pd
import subprocess
import threading
import time
import os
import sys
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(
    page_title="Kenya Flights",
    page_icon="✈",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
SCRAPER  = BASE_DIR / "scraper.py"

ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA", "from": "NBO", "to": "MBA"},
    "Nairobi → Kisumu":  {"label": "NBO→KIS", "from": "NBO", "to": "KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL", "from": "NBO", "to": "EDL"},
}

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2rem 2rem 2rem; max-width: 780px; }
.page-header { margin-bottom: 1.75rem; }
.page-header h1 { font-size: 20px; font-weight: 600; color: #0f0f0f; margin: 0 0 4px 0; }
.page-header p  { font-size: 13px; color: #6b7280; margin: 0; }
.search-panel { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:1.1rem 1.25rem; margin-bottom:1.25rem; }
.results-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:0.75rem; }
.results-count  { font-size:13px; color:#6b7280; }
.flight-card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:1rem 1.25rem; margin-bottom:10px; }
.flight-card.best-card { border:1.5px solid #0F6E56; }
.card-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.airline-row { display:flex; align-items:center; gap:10px; }
.airline-logo { width:30px; height:30px; border-radius:7px; background:#f3f4f6; border:1px solid #e5e7eb; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:600; color:#6b7280; }
.airline-name { font-size:14px; font-weight:500; color:#111827; }
.airline-date { font-size:12px; color:#9ca3af; margin-top:1px; }
.best-badge { font-size:11px; font-weight:500; padding:3px 9px; border-radius:20px; background:#E1F5EE; color:#0F6E56; border:1px solid #9FE1CB; }
.time-row { display:flex; align-items:center; margin-bottom:14px; }
.time-block .time { font-size:22px; font-weight:600; color:#111827; line-height:1.1; }
.time-block .iata { font-size:11px; color:#9ca3af; margin-top:2px; }
.route-line { flex:1; display:flex; flex-direction:column; align-items:center; gap:5px; padding:0 14px; }
.route-bar-wrap { width:100%; display:flex; align-items:center; }
.dot { width:5px; height:5px; border-radius:50%; background:#d1d5db; flex-shrink:0; }
.bar { flex:1; height:1px; background:#e5e7eb; }
.route-meta { display:flex; align-items:center; gap:8px; }
.duration { font-size:11px; color:#9ca3af; }
.stops-pill { font-size:11px; padding:2px 8px; border-radius:20px; background:#f3f4f6; border:1px solid #e5e7eb; color:#6b7280; }
.stops-pill.direct { background:#EAF3DE; border-color:#C0DD97; color:#3B6D11; }
.card-bottom { display:flex; align-items:center; justify-content:space-between; padding-top:12px; border-top:1px solid #f3f4f6; }
.price-kes { font-size:18px; font-weight:600; color:#111827; }
.price-usd { font-size:12px; color:#9ca3af; margin-top:1px; }
.book-btn  { font-size:13px; padding:7px 16px; border-radius:8px; border:1px solid #e5e7eb; background:#f9fafb; color:#374151; cursor:pointer; text-decoration:none; display:inline-block; }
.best-card .book-btn { background:#E1F5EE; border-color:#9FE1CB; color:#0F6E56; }
.status-running { background:rgba(0,153,255,.08); border:1px solid rgba(0,153,255,.2); color:#0369a1; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:8px; }
.status-success { background:rgba(0,180,120,.08); border:1px solid rgba(0,180,120,.2); color:#0F6E56; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:8px; }
.status-error   { background:rgba(220,38,38,.06); border:1px solid rgba(220,38,38,.2); color:#b91c1c; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:8px; }
.empty-state { text-align:center; padding:3rem 1rem; }
.empty-state h3 { font-size:15px; font-weight:500; color:#374151; margin-bottom:6px; }
.empty-state p  { font-size:13px; color:#9ca3af; }
label[data-testid="stWidgetLabel"] { font-size:11px !important; font-weight:500 !important; color:#9ca3af !important; text-transform:uppercase; letter-spacing:0.05em; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {"scrape_running": False, "scrape_status": "idle",
              "scrape_message": "", "scrape_log": "", "last_run": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Data loader — reads from Google Sheets ────────────────────────────────────
@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    try:
        from gsheets import read_flights
        df = read_flights()
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    for col, default in [("price_kes", 0), ("price_usd", 0), ("stops", 0), ("duration_mins", 0)]:
        if col not in df.columns:
            df[col] = default

    df["price_kes"]      = pd.to_numeric(df["price_kes"],      errors="coerce").fillna(0).astype(int)
    df["price_usd"]      = pd.to_numeric(df["price_usd"],      errors="coerce").fillna(0)
    df["stops"]          = pd.to_numeric(df["stops"],          errors="coerce").fillna(0).astype(int)
    df["duration_mins"]  = pd.to_numeric(df["duration_mins"],  errors="coerce")
    df["departure_time"] = df["departure_time"].astype(str).str.strip().replace("nan", "")
    df["arrival_time"]   = df["arrival_time"].astype(str).str.strip().replace("nan", "")
    df["flight_date"]    = df["flight_date"].astype(str).str.strip()
    return df.fillna("")

# ── Card renderer ─────────────────────────────────────────────────────────────
def render_card(row, is_best: bool, route_info: dict):
    airline   = str(row.get("airline", "Unknown"))
    initials  = "".join(w[0] for w in airline.split()[:2]).upper()
    dep       = row.get("departure_time") or "--:--"
    arr       = row.get("arrival_time")   or "--:--"
    stops     = int(row.get("stops", 0))
    price_kes = int(row.get("price_kes", 0))
    price_usd = int(float(row.get("price_usd", 0)))
    fdate     = row.get("flight_date", "")
    try:
        dm = int(float(row.get("duration_mins", 0) or 0))
        dur_label = f"{dm//60}h {dm%60:02d}m" if dm >= 60 else (f"{dm}m" if dm else "—")
    except Exception:
        dur_label = "—"

    stops_class = "stops-pill direct" if stops == 0 else "stops-pill"
    stops_label = "Direct" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
    card_class  = "flight-card best-card" if is_best else "flight-card"
    badge_html  = '<span class="best-badge">Best price</span>' if is_best else ""

    st.markdown(f"""
    <div class="{card_class}">
      <div class="card-top">
        <div class="airline-row">
          <div class="airline-logo">{initials}</div>
          <div><div class="airline-name">{airline}</div><div class="airline-date">{fdate}</div></div>
        </div>
        {badge_html}
      </div>
      <div class="time-row">
        <div class="time-block"><div class="time">{dep}</div><div class="iata">{route_info['from']}</div></div>
        <div class="route-line">
          <div class="route-bar-wrap"><div class="dot"></div><div class="bar"></div><div class="dot"></div></div>
          <div class="route-meta"><span class="duration">{dur_label}</span><span class="{stops_class}">{stops_label}</span></div>
        </div>
        <div class="time-block" style="text-align:right"><div class="time">{arr}</div><div class="iata">{route_info['to']}</div></div>
      </div>
      <div class="card-bottom">
        <div><div class="price-kes">KES {price_kes:,}</div><div class="price-usd">≈ USD {price_usd:,}</div></div>
        <a class="book-btn" href="#" onclick="return false;">View deal →</a>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Background scraper ────────────────────────────────────────────────────────
def run_scraper_thread(route_label=None, flight_date=None):
    st.session_state.scrape_running = True
    st.session_state.scrape_status  = "running"
    st.session_state.scrape_message = f"Scraping {route_label or 'all routes'}…"

    env = os.environ.copy()
    if route_label: env["SCRAPE_ROUTE"] = route_label
    if flight_date: env["SCRAPE_DATE"]  = str(flight_date)

    try:
        result = subprocess.run(
            [sys.executable, str(SCRAPER)],
            capture_output=True, text=True, timeout=360,
            env=env, cwd=str(BASE_DIR),
        )
        st.session_state.scrape_log = (result.stdout or "")[-2000:]
        if result.returncode == 0:
            st.session_state.scrape_status  = "success"
            st.session_state.scrape_message = "Done! New flights saved to Google Sheets."
        else:
            st.session_state.scrape_status  = "error"
            st.session_state.scrape_message = (result.stderr or "Unknown error")[-600:]
    except subprocess.TimeoutExpired:
        st.session_state.scrape_status  = "error"
        st.session_state.scrape_message = "Scraper timed out after 6 minutes."
    except Exception as e:
        st.session_state.scrape_status  = "error"
        st.session_state.scrape_message = str(e)
    finally:
        st.session_state.scrape_running = False
        st.session_state.last_run = time.strftime("%Y-%m-%d %H:%M:%S")
        load_data.clear()

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="page-header">
  <h1>✈ Kenya flights</h1>
  <p>Live domestic fare search — data stored in Google Sheets</p>
</div>
""", unsafe_allow_html=True)

# ── Scrape controls ───────────────────────────────────────────────────────────
with st.expander("🔄 Run scraper", expanded=False):
    sc1, sc2 = st.columns(2)
    with sc1:
        scrape_route = st.selectbox("Route to scrape", ["All routes"] + list(ROUTES.keys()), key="sr")
    with sc2:
        scrape_date = st.date_input("Date", value=date.today(),
                                    min_value=date.today(),
                                    max_value=date.today() + timedelta(days=30), key="sd")

    if st.button("▶ Fetch live prices", disabled=st.session_state.scrape_running,
                 type="primary", use_container_width=True):
        label = None if scrape_route == "All routes" else ROUTES[scrape_route]["label"]
        threading.Thread(target=run_scraper_thread, args=(label, scrape_date), daemon=True).start()
        st.rerun()

    s = st.session_state.scrape_status
    m = st.session_state.scrape_message
    if s == "running":
        st.markdown(f'<div class="status-running">⚡ {m}</div>', unsafe_allow_html=True)
    elif s == "success":
        st.markdown(f'<div class="status-success">✓ {m}</div>', unsafe_allow_html=True)
        if st.session_state.last_run:
            st.caption(f"Last run: {st.session_state.last_run}")
    elif s == "error":
        st.markdown('<div class="status-error">✗ Scraper error</div>', unsafe_allow_html=True)
        st.code(m, language="bash")
    if st.session_state.get("scrape_log"):
        with st.expander("Scraper log"):
            st.text(st.session_state.scrape_log)

# ── Search panel ──────────────────────────────────────────────────────────────
st.markdown('<div class="search-panel">', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    selected_route = st.selectbox("Route", list(ROUTES.keys()))
with col2:
    selected_date = st.date_input("Departure date", value=date.today(),
                                  min_value=date.today(),
                                  max_value=date.today() + timedelta(days=30))
auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=False)
st.markdown('</div>', unsafe_allow_html=True)

# ── Load + filter ─────────────────────────────────────────────────────────────
df = load_data()
route_info  = ROUTES[selected_route]
route_label = route_info["label"]
date_str    = str(selected_date)

if not df.empty:
    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] == date_str)
    ].sort_values("price_kes").reset_index(drop=True)
else:
    filtered = pd.DataFrame()

# ── Results ───────────────────────────────────────────────────────────────────
if st.button("↻ Refresh data"):
    load_data.clear()
    st.rerun()

if filtered.empty:
    if df.empty:
        st.markdown("""
        <div class="empty-state">
          <h3>No data yet</h3>
          <p>Expand "Run scraper" above and click Fetch live prices.</p>
        </div>""", unsafe_allow_html=True)
    else:
        available = df[df["route"] == route_label]["flight_date"].unique()
        hint = f"Available dates: {', '.join(sorted(available))}" if len(available) else "Try a different route."
        st.markdown(f"""
        <div class="empty-state">
          <h3>No flights found for {date_str}</h3>
          <p>{hint}</p>
        </div>""", unsafe_allow_html=True)
else:
    cheapest = filtered["price_kes"].min()
    st.markdown(f"""
    <div class="results-header">
      <span class="results-count">{len(filtered)} flight{'s' if len(filtered) != 1 else ''} found</span>
      <span style="font-size:12px;color:#9ca3af;">Sorted by price</span>
    </div>""", unsafe_allow_html=True)
    for _, row in filtered.iterrows():
        render_card(row, row["price_kes"] == cheapest, route_info)

if auto_refresh:
    time.sleep(30)
    load_data.clear()
    st.rerun()
