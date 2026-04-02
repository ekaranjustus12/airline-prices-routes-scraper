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
.block-container { padding: 1rem 1rem 2rem 1rem; max-width: 800px; }

/* ── Header ── */
.page-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 0 20px 0;
    border-bottom: 1px solid rgba(128,128,128,0.25);
    margin-bottom: 20px;
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
    color: inherit;
    margin: 0;
    line-height: 1.2;
}
.page-header-text p {
    font-size: 13px;
    color: rgba(128,128,128,0.85);
    margin: 3px 0 0 0;
}
.data-freshness {
    margin-left: auto;
    text-align: right;
    font-size: 12px;
    color: rgba(128,128,128,0.75);
    line-height: 1.6;
    flex-shrink: 0;
}
.data-freshness .freshness-time {
    font-size: 15px;
    font-weight: 700;
    color: inherit;
    display: block;
}
.data-freshness .freshness-date {
    font-size: 11px;
    color: rgba(128,128,128,0.7);
    display: block;
}

/* ── Search panel ── */
.search-panel {
    background: rgba(128,128,128,0.07);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 14px;
    padding: 1.1rem 1.2rem;
    margin-bottom: 1.25rem;
}

/* ── Flight card ── */
.flight-card {
    background: rgba(128,128,128,0.06);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin-bottom: 10px;
    transition: border-color 0.15s;
}
.flight-card.best-card { border: 1.5px solid #0F6E56; }

/* card top: airline + badge */
.card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    gap: 8px;
}
.airline-row { display:flex; align-items:center; gap:10px; min-width:0; }
.airline-logo {
    width: 34px; height: 34px; border-radius: 8px;
    background: rgba(128,128,128,0.15);
    border: 1px solid rgba(128,128,128,0.2);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; color: inherit;
    flex-shrink: 0;
}
.airline-name {
    font-size: 14px; font-weight: 600; color: inherit;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.airline-date { font-size: 11px; color: rgba(128,128,128,0.85); margin-top: 1px; }
.best-badge {
    font-size: 10px; font-weight: 600;
    padding: 3px 8px; border-radius: 20px;
    background: #E1F5EE; color: #0F6E56;
    border: 1px solid #9FE1CB;
    white-space: nowrap; flex-shrink: 0;
}

/* time row */
.time-row { display:flex; align-items:center; margin-bottom:12px; }
.time-block .time {
    font-size: 22px; font-weight: 700; color: inherit; line-height: 1;
}
.time-block .iata {
    font-size: 11px; color: rgba(128,128,128,0.85);
    margin-top: 3px; letter-spacing: 0.05em;
}
.route-line {
    flex: 1; display:flex; flex-direction:column;
    align-items:center; gap:5px; padding: 0 10px;
}
.route-bar-wrap { width:100%; display:flex; align-items:center; }
.dot { width:5px; height:5px; border-radius:50%; background:rgba(128,128,128,0.4); flex-shrink:0; }
.bar { flex:1; height:1px; background:rgba(128,128,128,0.25); }
.route-meta { display:flex; align-items:center; gap:6px; flex-wrap:wrap; justify-content:center; }
.duration { font-size: 10px; color: rgba(128,128,128,0.75); }
.stops-pill {
    font-size: 10px; padding: 2px 7px; border-radius: 20px;
    background: rgba(128,128,128,0.12);
    border: 1px solid rgba(128,128,128,0.2);
    color: rgba(128,128,128,0.9);
}
.stops-pill.direct {
    background: #EAF3DE; border-color: #C0DD97; color: #3B6D11; font-weight: 500;
}

/* card bottom: price */
.card-bottom {
    display: flex; align-items: center; justify-content: space-between;
    padding-top: 10px;
    border-top: 1px solid rgba(128,128,128,0.15);
}
.price-kes { font-size: 20px; font-weight: 700; color: inherit; }
.price-usd { font-size: 11px; color: rgba(128,128,128,0.75); margin-top: 2px; }

/* ── Mobile: stack time row vertically on small screens ── */
@media (max-width: 480px) {
    .block-container { padding: 0.75rem 0.5rem 2rem 0.5rem !important; }
    .page-header-text h1 { font-size: 18px; }
    .time-block .time { font-size: 20px; }
    .time-row { gap: 4px; }
    .route-line { padding: 0 6px; }
    .price-kes { font-size: 18px; }
    .flight-card { padding: 0.85rem 0.9rem; }
    .data-freshness .freshness-time { font-size: 13px; }
}

/* ── Empty state ── */
.empty-state {
    text-align: center; padding: 3rem 1rem;
    background: rgba(128,128,128,0.06);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 14px;
}
.empty-state h3 { font-size:16px; font-weight:600; color:inherit; margin-bottom:6px; }
.empty-state p  { font-size:13px; color:rgba(128,128,128,0.75); margin:0; }

/* ── Summary row ── */
.results-meta { margin-bottom: 10px; }
.results-count { font-size: 12px; color: rgba(128,128,128,0.75); }

/* Tighten Streamlit widget labels */
label[data-testid="stWidgetLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: rgba(128,128,128,0.8) !important;
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

# Format last_scraped as time + date on separate lines
freshness_html = ""
if not df.empty and "date_scraped" in df.columns:
    try:
        raw = df["date_scraped"].max()
        ts  = pd.to_datetime(raw)
        t   = ts.strftime("%H:%M")               # "14:00"
        d   = ts.strftime("%d %B").lstrip("0")   # "2 April" (strip leading zero)
        freshness_html = f'''
        <div class="data-freshness">
          <span class="freshness-time">{t}</span>
          <span class="freshness-date">{d}</span>
        </div>'''
    except Exception:
        freshness_html = ""

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="page-header">
  <div class="page-header-icon">✈</div>
  <div class="page-header-text">
    <h1>Domestic Flights</h1>
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
