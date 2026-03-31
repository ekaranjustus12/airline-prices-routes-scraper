import streamlit as st
import pandas as pd
import time
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Page config ───────────────────────────────────────
st.set_page_config(
    page_title="Kenya Flights",
    page_icon="✈",
    layout="wide"
)

# ── Paths ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "kenya_flights_esky.csv"

# ── Routes ────────────────────────────────────────────
ROUTES = {
    "Nairobi → Mombasa": {"label": "NBO→MBA", "from": "NBO", "to": "MBA"},
    "Nairobi → Kisumu":  {"label": "NBO→KIS", "from": "NBO", "to": "KIS"},
    "Nairobi → Eldoret": {"label": "NBO→EDL", "from": "NBO", "to": "EDL"},
}

# ── Load data safely ──────────────────────────────────
@st.cache_data(ttl=60)
def load_data():
    if not CSV_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_FILE)

        # Ensure required columns exist
        required_cols = [
            "route", "flight_date", "price_kes",
            "departure_time", "arrival_time"
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        # Clean data
        df["price_kes"] = pd.to_numeric(df["price_kes"], errors="coerce").fillna(0)
        df["price_usd"] = pd.to_numeric(df.get("price_usd", 0), errors="coerce").fillna(0)
        df["stops"] = pd.to_numeric(df.get("stops", 0), errors="coerce").fillna(0)

        df["departure_time"] = pd.to_datetime(
            df["departure_time"], errors="coerce"
        ).dt.strftime("%H:%M")

        df["arrival_time"] = pd.to_datetime(
            df["arrival_time"], errors="coerce"
        ).dt.strftime("%H:%M")

        df["flight_date"] = df["flight_date"].astype(str)

        return df

    except Exception as e:
        st.error(f"Error reading data: {e}")
        return pd.DataFrame()

# ── Run scraper safely ─────────────────────────────────
def run_scraper():
    scraper_path = BASE_DIR / "scraper.py"

    if not scraper_path.exists():
        st.error("scraper.py not found")
        return

    with st.spinner("Fetching latest flights... (30–90 seconds)"):
        try:
            result = subprocess.run(
                [sys.executable, str(scraper_path)],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(BASE_DIR)
            )

            # Show logs (important for debugging)
            if result.stdout:
                st.text(result.stdout[-1000:])

            # Instead of relying on returncode → check file
            if CSV_FILE.exists() and os.path.getsize(CSV_FILE) > 0:
                st.cache_data.clear()
                st.success("Flights updated!")
            else:
                st.warning("No new data scraped. Showing last available results.")

        except subprocess.TimeoutExpired:
            st.error("Scraper timed out. Try again.")
        except Exception as e:
            st.error(f"Error running scraper: {e}")

# ── UI Header ─────────────────────────────────────────
st.title("✈ Kenya Flights")
st.caption("Live domestic fare search")

# ── Controls ──────────────────────────────────────────
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

col3, col4 = st.columns([3, 1])

with col3:
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

with col4:
    if st.button("🔄 Fetch flights"):
        run_scraper()

# ── Load + filter data ────────────────────────────────
df = load_data()

route_info = ROUTES[selected_route]
route_label = route_info["label"]
date_str = str(selected_date)

if not df.empty:
    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] >= date_str)
    ].sort_values("price_kes")
else:
    filtered = pd.DataFrame()

# ── Display results ───────────────────────────────────
if filtered.empty:
    st.warning("No flights found. Click 'Fetch flights' to load data.")
else:
    st.success(f"{len(filtered)} flights found")

    cheapest = filtered["price_kes"].min()

    for _, row in filtered.iterrows():
        is_best = row["price_kes"] == cheapest

        with st.container():
            colA, colB, colC = st.columns([2, 2, 2])

            with colA:
                st.markdown(f"**{row.get('airline', 'Unknown')}**")
                st.caption(row.get("flight_date", ""))

            with colB:
                st.markdown(
                    f"{row.get('departure_time','--')} → {row.get('arrival_time','--')}"
                )
                stops = int(row.get("stops", 0))
                st.caption("Direct" if stops == 0 else f"{stops} stop(s)")

            with colC:
                st.markdown(f"**KES {int(row.get('price_kes',0)):,}**")
                if is_best:
                    st.caption("✅ Best price")

            st.divider()

# ── Auto refresh ──────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
