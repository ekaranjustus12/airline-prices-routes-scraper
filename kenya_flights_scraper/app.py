import install_playwright  # noqa: F401 — must be first line

import streamlit as st
import pandas as pd
import time
import subprocess
import sys
import os
from datetime import date, timedelta
from pathlib import Path

# ── Page Config ─────────────────────────────────────────
st.set_page_config(
    page_title="Kenya Flights",
    page_icon="✈",
    layout="wide"
)

# ── Constants ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "kenya_flights_esky.csv"

ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA"},
    "Nairobi → Kisumu": {"label": "NBO→KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL"},
}

# ── Scraper Runner ──────────────────────────────────────
def run_scraper(route_label, selected_date):
    env = os.environ.copy()
    env["SCRAPE_ROUTE"] = route_label
    env["SCRAPE_DATE"] = str(selected_date)

    result = subprocess.run(
        [sys.executable, "scraper.py"],
        capture_output=True,
        text=True,
        env=env
    )

    return result

# ── Load Data ───────────────────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_FILE)

    if df.empty:
        return df

    # Clean numeric fields
    df["price_kes"] = pd.to_numeric(df.get("price_kes", 0), errors="coerce").fillna(0)
    df["price_usd"] = pd.to_numeric(df.get("price_usd", 0), errors="coerce").fillna(0)
    df["stops"] = pd.to_numeric(df.get("stops", 0), errors="coerce").fillna(0)

    # Format time
    df["departure_time"] = pd.to_datetime(df["departure_time"], errors="coerce").dt.strftime("%H:%M")
    df["arrival_time"] = pd.to_datetime(df["arrival_time"], errors="coerce").dt.strftime("%H:%M")

    # Normalize date properly
    df["flight_date"] = pd.to_datetime(df["flight_date"], errors="coerce").dt.date

    return df

# ── UI ──────────────────────────────────────────────────
st.markdown("# ✈ Kenya Flights Search")
st.caption("Real-time flight search (Powered by scraper)")

# Inputs
col1, col2 = st.columns(2)

with col1:
    selected_route = st.selectbox("Route", list(ROUTES.keys()))

with col2:
    selected_date = st.date_input(
        "Departure Date",
        value=date.today(),
        min_value=date.today(),
        max_value=date.today() + timedelta(days=30)
    )

route_label = ROUTES[selected_route]["label"]

# ── Scraper Trigger Button ──────────────────────────────
if st.button("🔄 Fetch Latest Flights"):
    with st.spinner("Scraping flights... this may take 30–90 seconds ⏳"):

        result = run_scraper(route_label, selected_date)

        if result.returncode == 0:
            st.success("✅ Flights updated successfully!")
        else:
            st.error("❌ Scraper failed")

        # Logs (VERY IMPORTANT)
        with st.expander("📄 Scraper Logs"):
            st.text(result.stdout)
            st.text(result.stderr)

        st.cache_data.clear()
        st.rerun()

# ── Load Data ───────────────────────────────────────────
df = load_data()

# ── Debug Section ───────────────────────────────────────
with st.expander("🛠 Debug Info"):
    st.write("CSV path:", CSV_FILE)
    st.write("File exists:", CSV_FILE.exists())

    if CSV_FILE.exists():
        st.write("File size:", CSV_FILE.stat().st_size)

    if not df.empty:
        st.write("Preview:", df.head())
        st.write("Available routes:", df["route"].unique())
    else:
        st.warning("No data loaded yet")

# ── Filter Data ─────────────────────────────────────────
if not df.empty:
    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] == selected_date)
    ]
else:
    filtered = pd.DataFrame()

# ── Display ─────────────────────────────────────────────
st.markdown("---")

if filtered.empty:
    st.markdown("""
    <div style='text-align:center;padding:40px'>
        <h3>No flights found</h3>
        <p>Click "Fetch Latest Flights" to scrape data</p>
    </div>
    """, unsafe_allow_html=True)

else:
    filtered = filtered.sort_values("price_kes")

    st.subheader(f"{len(filtered)} Flights Found")

    cheapest_price = filtered["price_kes"].min()

    for _, row in filtered.iterrows():
        is_cheapest = row["price_kes"] == cheapest_price
        badge = "🟢 BEST PRICE" if is_cheapest else ""

        st.markdown(f"""
        ### ✈ {row.get('airline', 'Unknown')} {badge}
        **Route:** {row.get('route')}
        
        🕐 {row.get('departure_time')} → {row.get('arrival_time')}  
        ⏱ Duration: {row.get('duration_mins')} mins  
        🛑 Stops: {row.get('stops')}
        
        💰 **KES {int(row.get('price_kes', 0)):,}**
        ---
        """)

# ── Auto Refresh ───────────────────────────────────────
refresh = st.checkbox("Auto-refresh every 10 seconds")

if refresh:
    time.sleep(10)
    st.cache_data.clear()
    st.rerun()

# ── Footer ─────────────────────────────────────────────
st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")
