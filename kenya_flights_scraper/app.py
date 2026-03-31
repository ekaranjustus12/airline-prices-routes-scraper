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

        # Ensure required columns exist with correct defaults
        required_cols = {
            "route": "",
            "flight_date": "",
            "price_kes": 0,
            "departure_time": "",
            "arrival_time": "",
            "price_usd": 0.0,
            "stops": 0,
            "airline": "Unknown",
        }
        for col, default in required_cols.items():
            if col not in df.columns:
                df[col] = default

        # FIX: use df[col] not df.get(col) — DataFrame.get() returns a
        # scalar default for missing columns, which breaks pd.to_numeric
        df["price_kes"] = pd.to_numeric(df["price_kes"], errors="coerce").fillna(0).astype(int)
        df["price_usd"] = pd.to_numeric(df["price_usd"], errors="coerce").fillna(0.0)
        df["stops"]     = pd.to_numeric(df["stops"],     errors="coerce").fillna(0).astype(int)

        # FIX: departure/arrival are stored as bare "HH:MM" strings in the CSV.
        # pd.to_datetime("14:30") returns NaT — just clean them as strings instead.
        df["departure_time"] = df["departure_time"].astype(str).str.strip().replace("nan", "")
        df["arrival_time"]   = df["arrival_time"].astype(str).str.strip().replace("nan", "")

        df["flight_date"] = df["flight_date"].astype(str).str.strip()

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

            if result.stdout:
                st.text(result.stdout[-1500:])

            if result.stderr:
                st.text("Stderr: " + result.stderr[-500:])

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
    # FIX: was `>= date_str` which returned all future dates regardless
    # of what the user selected. Use == to match the chosen date only.
    filtered = df[
        (df["route"] == route_label) &
        (df["flight_date"] == date_str)
    ].sort_values("price_kes")
else:
    filtered = pd.DataFrame()

# ── Display results ───────────────────────────────────
if filtered.empty:
    if df.empty:
        st.warning("No data yet. Click '🔄 Fetch flights' to load data.")
    else:
        # Show which dates DO have data for this route, to help the user
        route_dates = df[df["route"] == route_label]["flight_date"].unique()
        if len(route_dates):
            st.warning(
                f"No flights for {route_label} on {date_str}. "
                f"Available dates: {', '.join(sorted(route_dates))}"
            )
        else:
            st.warning(f"No flights found for {route_label}. Click '🔄 Fetch flights'.")
else:
    st.success(f"{len(filtered)} flight(s) found for {route_label} on {date_str}")

    cheapest = filtered["price_kes"].min()

    for _, row in filtered.iterrows():
        is_best = row["price_kes"] == cheapest

        with st.container():
            colA, colB, colC = st.columns([2, 2, 2])

            with colA:
                st.markdown(f"**{row.get('airline', 'Unknown')}**")
                st.caption(row.get("flight_date", ""))

            with colB:
                dep = row.get("departure_time", "") or "--"
                arr = row.get("arrival_time", "") or "--"
                st.markdown(f"{dep} → {arr}")
                stops = int(row.get("stops", 0))
                st.caption("Direct" if stops == 0 else f"{stops} stop(s)")

            with colC:
                st.markdown(f"**KES {int(row.get('price_kes', 0)):,}**")
                if is_best:
                    st.caption("✅ Best price")

            st.divider()

# ── Auto refresh ──────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
