import install_playwright  # noqa: F401

import streamlit as st
import pandas as pd
import time
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(page_title="Kenya Flights", page_icon="✈", layout="wide")

CSV_FILE = Path(__file__).parent / "kenya_flights_esky.csv"

ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA", "from": "NBO", "to": "MBA"},
    "Nairobi → Kisumu":  {"label": "NBO→KIS", "from": "NBO", "to": "KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL", "from": "NBO", "to": "EDL"},
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2rem 2rem 2rem; max-width: 800px; }

/* ── Header ── */
.page-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 20px 0 24px 0;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 24px;
}
.page-header-icon {
    width: 44px; height: 44px;
    background: #0F6E56;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; line-height: 1;
    flex-shrink: 0;
}
.page-header-text h1 {
    font-size: 22px;
    font-weight: 700;
    color: #0f0f0f;
    margin: 0;
    line-height: 1.2;
}
.page-header-text p {
    font-size: 13px;
    color: #6b7280;
    margin: 3px 0 0 0;
}
.data-freshness {
    margin-left: auto;
    text-align: right;
    font-size: 12px;
    color: #9ca3af;
    line-height: 1.5;
}
.data-freshness strong { color: #374151; font-weight: 500; }

/* ── Search panel ── */
.search-panel {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1.5rem;
}

/* ── Flight card ── */
.flight-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 10px;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.flight-card:hover { border-color: #d1d5db; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
.flight-card.best-card { border: 1.5px solid #0F6E56; }

.card-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
.airline-row { display:flex; align-items:center; gap:10px; }
.airline-logo {
    width: 36px; height: 36px; border-radius: 9px;
    background: #f3f4f6; border: 1px solid #e5e7eb;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: #4b5563;
}
.airline-name { font-size: 15px; font-weight: 600; color: #111827; }
.airline-date { font-size: 12px; color: #9ca3af; margin-top: 2px; }
.best-badge {
    font-size: 11px; font-weight: 600;
    padding: 4px 10px; border-radius: 20px;
    background: #E1F5EE; color: #0F6E56;
    border: 1px solid #9FE1CB;
    white-space: nowrap;
}

.time-row { display:flex; align-items:center; margin-bottom:14px; }
.time-block .time { font-size: 24px; font-weight: 700; color: #111827; line-height: 1; }
.time-block .iata { font-size: 11px; color: #9ca3af; margin-top: 3px; letter-spacing: 0.05em; }
.route-line { flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; padding:0 16px; }
.route-bar-wrap { width:100%; display:flex; align-items:center; }
.dot { width:5px; height:5px; border-radius:50%; background:#d1d5db; flex-shrink:0; }
.bar { flex:1; height:1px; background:#e5e7eb; }
.route-meta { display:flex; align-items:center; gap:8px; }
.duration { font-size: 11px; color: #9ca3af; }
.stops-pill { font-size:11px; padding:2px 9px; border-radius:20px; background:#f3f4f6; border:1px solid #e5e7eb; color:#6b7280; }
.stops-pill.direct { background:#EAF3DE; border-color:#C0DD97; color:#3B6D11; font-weight:500; }

.card-bottom { display:flex; align-items:center; justify-content:space-between; padding-top:12px; border-top:1px solid #f3f4f6; }
.price-kes { font-size: 20px; font-weight: 700; color: #111827; }
.price-usd { font-size: 12px; color: #9ca3af; margin-top: 2px; }

/* ── Empty state ── */
.empty-state { text-align:center; padding:3.5rem 1rem; background:#f9fafb; border:1px solid #e5e7eb; border-radius:14px; }
.empty-state h3 { font-size:16px; font-weight:600; color:#374151; margin-bottom:6px; }
.empty-state p  { font-size:13px; color:#9ca3af; margin:0; }

/* ── Summary row ── */
.results-meta { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.results-count { font-size:13px; color:#6b7280; }

/* Tighten Streamlit widget labels */
label[data-testid="stWidgetLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #6b7280 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
</style>
""", unsafe_allow_html=True)


# ── Data loader ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)   # re-read every 5 min; CSV only changes when GitHub Action commits
def load_data() -> pd.DataFrame:
    if not CSV_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_FILE)

    for col, default in [("price_kes",0),("price_usd",0),("stops",0),("duration_mins",0)]:
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


# ── Card renderer ─────────────────────────────────────────────────────────────
def render_card(row: dict, is_best: bool, route_info: dict):
    airline   = str(row.get("airline", "Unknown"))
    initials  = "".join(w[0] for w in airline.split()[:2]).upper()
    dep       = row.get("departure_time") or "—"
    arr       = row.get("arrival_time")   or "—"
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
    badge       = '<span class="best-badge">★ Best price</span>' if is_best else ""

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
        {badge}
      </div>
      <div class="time-row">
        <div class="time-block">
          <div class="time">{dep}</div>
          <div class="iata">{route_info['from']}</div>
        </div>
        <div class="route-line">
          <div class="route-bar-wrap">
            <div class="dot"></div><div class="bar"></div><div class="dot"></div>
          </div>
          <div class="route-meta">
            <span class="duration">{dur_label}</span>
            <span class="{stops_class}">{stops_label}</span>
          </div>
        </div>
        <div class="time-block" style="text-align:right">
          <div class="time">{arr}</div>
          <div class="iata">{route_info['to']}</div>
        </div>
      </div>
      <div class="card-bottom">
        <div>
          <div class="price-kes">KES {price_kes:,}</div>
          <div class="price-usd">≈ USD {price_usd}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────
df = load_data()

# Work out when the CSV was last updated
if not df.empty and "date_scraped" in df.columns:
    last_scraped = df["date_scraped"].max()
else:
    last_scraped = None

# ── Header ────────────────────────────────────────────────────────────────────
freshness_html = (
    f'<div class="data-freshness">Data updated<br><strong>{last_scraped}</strong></div>'
    if last_scraped else ""
)
st.markdown(f"""
<div class="page-header">
  <div class="page-header-icon">✈</div>
  <div class="page-header-text">
    <h1>Kenya Flights</h1>
    <p>Domestic fare prices — NBO routes</p>
  </div>
  {freshness_html}
</div>
""", unsafe_allow_html=True)

# ── Search controls ───────────────────────────────────────────────────────────
st.markdown('<div class="search-panel">', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    selected_route = st.selectbox("Route", list(ROUTES.keys()), label_visibility="visible")
with col2:
    # Only show dates that actually exist in the data for this route
    route_label = ROUTES[selected_route]["label"]
    if not df.empty:
        available_dates = sorted(
            df[df["route"] == route_label]["flight_date"].dropna().unique().tolist()
        )
    else:
        available_dates = []

    if available_dates:
        selected_date = st.selectbox("Departure date", available_dates, label_visibility="visible")
    else:
        selected_date = st.selectbox("Departure date", ["No data yet"], label_visibility="visible")

st.markdown('</div>', unsafe_allow_html=True)

# ── Filter ────────────────────────────────────────────────────────────────────
if not df.empty and selected_date != "No data yet":
    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] == selected_date)
    ].sort_values("price_kes").reset_index(drop=True)
else:
    filtered = pd.DataFrame()

# ── Results ───────────────────────────────────────────────────────────────────
if filtered.empty:
    if df.empty:
        st.markdown("""
        <div class="empty-state">
          <h3>No data yet</h3>
          <p>Commit <code>kenya_flights_esky.csv</code> to your repo,<br>
             or wait for the scheduled scraper to run.</p>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="empty-state">
          <h3>No flights found</h3>
          <p>No data for {selected_route} on {selected_date}.</p>
        </div>""", unsafe_allow_html=True)
else:
    route_info = ROUTES[selected_route]
    cheapest   = filtered["price_kes"].min()

    st.markdown(f"""
    <div class="results-meta">
      <span class="results-count">{len(filtered)} flight{'s' if len(filtered)!=1 else ''} · {selected_route} · {selected_date}</span>
    </div>""", unsafe_allow_html=True)

    for _, row in filtered.iterrows():
        render_card(row.to_dict(), row["price_kes"] == cheapest, route_info)
