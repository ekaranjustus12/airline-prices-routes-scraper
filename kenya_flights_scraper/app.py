import install_playwright  # noqa: F401  — must be first line

import streamlit as st
import pandas as pd
import time
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(
    page_title="Kenya Flights",
    page_icon="✈",
    layout="wide"
)

# ── CSV path — file sits in the same folder as app.py in the GitHub repo ──────
CSV_FILE = Path(__file__).parent / "kenya_flights_esky.csv"

ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA", "from": "NBO", "to": "MBA"},
    "Nairobi → Kisumu":  {"label": "NBO→KIS", "from": "NBO", "to": "KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL", "from": "NBO", "to": "EDL"},
}

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
.empty-state { text-align:center; padding:3rem 1rem; }
.empty-state h3 { font-size:15px; font-weight:500; color:#374151; margin-bottom:6px; }
.empty-state p  { font-size:13px; color:#9ca3af; }
label[data-testid="stWidgetLabel"] { font-size:11px !important; font-weight:500 !important; color:#9ca3af !important; text-transform:uppercase; letter-spacing:0.05em; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    if not CSV_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_FILE)

    for col, default in [("price_kes", 0), ("price_usd", 0), ("stops", 0), ("duration_mins", 0)]:
        if col not in df.columns:
            df[col] = default

    df["price_kes"]      = pd.to_numeric(df["price_kes"],     errors="coerce").fillna(0).astype(int)
    df["price_usd"]      = pd.to_numeric(df["price_usd"],     errors="coerce").fillna(0)
    df["stops"]          = pd.to_numeric(df["stops"],         errors="coerce").fillna(0).astype(int)
    df["duration_mins"]  = pd.to_numeric(df["duration_mins"], errors="coerce")
    df["departure_time"] = df["departure_time"].astype(str).str.strip().replace("nan", "")
    df["arrival_time"]   = df["arrival_time"].astype(str).str.strip().replace("nan", "")
    df["flight_date"]    = df["flight_date"].astype(str).str.strip()
    return df.fillna("")


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
        dm = int(float(row.get("duration_mins") or 0))
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
        <div class="time-block" style="text-align:right">
          <div class="time">{arr}</div><div class="iata">{route_info['to']}</div>
        </div>
      </div>
      <div class="card-bottom">
        <div><div class="price-kes">KES {price_kes:,}</div><div class="price-usd">≈ USD {price_usd:,}</div></div>
        <a class="book-btn" href="#" onclick="return false;">View deal →</a>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Page ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-header">
  <h1>✈ Kenya flights</h1>
  <p>Live domestic fare search</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="search-panel">', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    selected_route = st.selectbox("Route", list(ROUTES.keys()))
with col2:
    selected_date = st.date_input(
        "Departure date",
        value=date.today(),
        min_value=date.today(),
        max_value=date.today() + timedelta(days=30),
    )
auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=False)
st.markdown('</div>', unsafe_allow_html=True)

# ── Load + filter ─────────────────────────────────────────────────────────────
df          = load_data()
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
if st.button("↻ Refresh"):
    load_data.clear()
    st.rerun()

if filtered.empty:
    if df.empty:
        st.markdown("""
        <div class="empty-state">
          <h3>No data yet</h3>
          <p>Commit <code>kenya_flights_esky.csv</code> to your GitHub repo to display flights.</p>
        </div>""", unsafe_allow_html=True)
    else:
        available = df[df["route"] == route_label]["flight_date"].unique()
        hint = f"Available dates: {', '.join(sorted(available))}" if len(available) else "Try a different route."
        st.markdown(f"""
        <div class="empty-state">
          <h3>No flights for {date_str}</h3>
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
