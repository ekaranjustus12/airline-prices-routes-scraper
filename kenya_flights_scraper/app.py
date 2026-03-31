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

# ── Constants ─────────────────────────────────────────────────────────────────
# On Streamlit Cloud the CSV lives next to app.py in the repo/working dir.
# (On Colab it was on Google Drive — that path won't exist here.)
CSV_FILE = Path(__file__).parent / "kenya_flights_esky.csv"

ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA"},
    "Nairobi → Kisumu": {"label": "NBO→KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL"},
}




# ── Load Data ─────────────────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(CSV_FILE)

    # Clean numeric fields
    df["price_kes"] = pd.to_numeric(df.get("price_kes", 0), errors="coerce").fillna(0)
    df["price_usd"] = pd.to_numeric(df.get("price_usd", 0), errors="coerce").fillna(0)
    df["stops"] = pd.to_numeric(df.get("stops", 0), errors="coerce").fillna(0)

    # Format time (VERY IMPORTANT)
    df["departure_time"] = pd.to_datetime(df["departure_time"], errors="coerce").dt.strftime("%H:%M")
    df["arrival_time"] = pd.to_datetime(df["arrival_time"], errors="coerce").dt.strftime("%H:%M")

    # Normalize date
    df["flight_date"] = df["flight_date"].astype(str)

    return df


# ── UI ────────────────────────────────────────────────
st.markdown("# ✈ Kenya Flights Search")
st.caption("Real-time flight search")

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

# ── Load Data ─────────────────────────────────────────
df = load_data()

# ── FIXED FILTER (SMART DATE RANGE) ───────────────────
if not df.empty:
    selected_date_str = str(selected_date)

    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] >= selected_date_str)
    ]
else:
    filtered = pd.DataFrame()

# ── Display ───────────────────────────────────────────
st.markdown("---")

if filtered.empty:
    st.markdown("""
    <div style='text-align:center;padding:40px'>
        <h3>No flights found</h3>
        <p>Try another route or date</p>
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

# ── SAFE AUTO REFRESH (FIXED) ─────────────────────────
refresh = st.checkbox("Auto-refresh every 10 seconds")

if refresh:
    time.sleep(10)
    st.cache_data.clear()
    st.rerun()

st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")
