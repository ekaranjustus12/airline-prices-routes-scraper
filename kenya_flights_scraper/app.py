# ── MUST be first — installs Chromium binary on Streamlit Cloud ───────────────
import install_playwright  # noqa: F401

import streamlit as st
import pandas as pd
import subprocess
import threading
import time
import os
import sys
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(page_title="Kenya Flights", page_icon="✈", layout="wide", initial_sidebar_state="expanded")

BASE_DIR   = Path(__file__).parent
CSV_FILE   = BASE_DIR / "kenya_flights_esky.csv"
SCRAPER    = BASE_DIR / "scraper.py"
USD_TO_KES = 130

ROUTES = {
    "Nairobi → Mombasa": {"from_code": "NAIR", "to_code": "MBA", "label": "NBO→MBA"},
    "Nairobi → Kisumu":  {"from_code": "NAIR", "to_code": "KIS", "label": "NBO→KIS"},
    "Nairobi → Eldoret": {"from_code": "NAIR", "to_code": "EDL", "label": "NBO→EDL"},
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
[data-testid="metric-container"] { background:#111827;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:18px 20px !important;position:relative;overflow:hidden; }
[data-testid="metric-container"]::before { content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#00d4aa,#0099ff); }
[data-testid="stMetricValue"] { font-family:'Syne',sans-serif !important;font-size:1.6rem !important;font-weight:800 !important;color:#00d4aa !important; }
[data-testid="stMetricLabel"] { color:#7a8ba0 !important;font-size:0.75rem !important; }
[data-testid="stSidebar"] { background:#111827 !important;border-right:1px solid rgba(255,255,255,0.07) !important; }
[data-testid="stSidebar"] .stSelectbox label,[data-testid="stSidebar"] .stDateInput label,[data-testid="stSidebar"] .stRadio label,[data-testid="stSidebar"] p { color:#e8edf5 !important; }
.flight-card { background:#111827;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:18px 22px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;gap:16px;transition:border-color .2s; }
.flight-card:hover { border-color:rgba(255,255,255,0.15); }
.flight-card.cheapest { border-color:rgba(0,212,170,0.35) !important; }
.fc-badge{font-size:9px;font-weight:700;letter-spacing:.1em;color:#00d4aa;margin-bottom:6px;display:block}
.fc-airline{font-size:15px;font-weight:600;color:#e8edf5}.fc-route{font-size:12px;color:#7a8ba0;margin-top:2px}
.fc-time-block{text-align:center}.fc-time{font-family:'Syne',sans-serif;font-size:22px;font-weight:700;color:#e8edf5;line-height:1}
.fc-tlabel{font-size:10px;color:#7a8ba0;margin-top:2px}.fc-dur{font-size:11px;color:#7a8ba0;text-align:center;padding:0 8px}
.stops-direct{background:rgba(0,212,170,.1);color:#00d4aa;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:500}
.stops-one{background:rgba(245,158,11,.1);color:#f59e0b;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:500}
.stops-multi{background:rgba(239,68,68,.1);color:#ef4444;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:500}
.fc-price-kes{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#00d4aa;line-height:1;text-align:right}
.fc-price-usd{font-size:11px;color:#7a8ba0;text-align:right;margin-top:2px}
.fc-src-api{font-size:10px;background:rgba(0,153,255,.12);color:#0099ff;padding:1px 7px;border-radius:6px}
.fc-src-html{font-size:10px;background:rgba(245,158,11,.12);color:#f59e0b;padding:1px 7px;border-radius:6px}
.section-head{font-family:'Syne',sans-serif;font-size:13px;font-weight:700;letter-spacing:.08em;color:#7a8ba0;text-transform:uppercase;margin-bottom:14px}
.status-running{background:rgba(0,153,255,.1);border:1px solid rgba(0,153,255,.2);color:#0099ff;border-radius:8px;padding:10px 14px;font-size:13px}
.status-success{background:rgba(0,212,170,.1);border:1px solid rgba(0,212,170,.2);color:#00d4aa;border-radius:8px;padding:10px 14px;font-size:13px}
.status-error{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);color:#ef4444;border-radius:8px;padding:10px 14px;font-size:13px}
.empty-state{text-align:center;padding:60px 20px;background:#111827;border:1px solid rgba(255,255,255,0.07);border-radius:16px;color:#7a8ba0}
</style>
""", unsafe_allow_html=True)

defaults = {"scrape_running":False,"scrape_status":"idle","scrape_message":"","scrape_log":"","last_run":None,"auto_refresh":False}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v

@st.cache_data(ttl=15)
def load_data() -> pd.DataFrame:
    empty = pd.DataFrame(columns=["date_scraped","flight_date","route","departure_time","arrival_time","duration_mins","airline","stops","price_usd","price_kes","source"])
    if not CSV_FILE.exists(): return empty
    try: df = pd.read_csv(CSV_FILE)
    except Exception: return empty
    for col,default in [("price_kes",0),("price_usd",0.0),("stops",0),("duration_mins",0)]:
        if col not in df.columns: df[col]=default
    df["price_kes"]     = pd.to_numeric(df["price_kes"],    errors="coerce").fillna(0).astype(int)
    df["price_usd"]     = pd.to_numeric(df["price_usd"],    errors="coerce").fillna(0.0).round(2)
    df["stops"]         = pd.to_numeric(df["stops"],        errors="coerce").fillna(0).astype(int)
    df["duration_mins"] = pd.to_numeric(df["duration_mins"],errors="coerce")
    df["departure_time"]= df["departure_time"].astype(str).str.strip().replace("nan","")
    df["arrival_time"]  = df["arrival_time"].astype(str).str.strip().replace("nan","")
    df["flight_date"]   = df["flight_date"].astype(str).str.strip()
    return df.fillna("")

def fmt_kes(n): return f"KES {int(n):,}"
def fmt_dur(m):
    try:
        m=int(float(m)); return f"{m//60}h {m%60:02d}m" if m>=60 else f"{m}m"
    except: return "—"
def stops_badge(n):
    if n==0: return '<span class="stops-direct">Direct</span>'
    if n==1: return '<span class="stops-one">1 stop</span>'
    return f'<span class="stops-multi">{n} stops</span>'
def src_badge(s):
    if str(s).lower()=="api": return '<span class="fc-src-api">API</span>'
    return '<span class="fc-src-html">HTML</span>'

def render_flight_card(row:dict,is_cheapest:bool=False)->str:
    badge='<span class="fc-badge">★ BEST PRICE ON THIS ROUTE</span>' if is_cheapest else ""
    dep=row.get("departure_time") or "—"; arr=row.get("arrival_time") or "—"
    dur=fmt_dur(row.get("duration_mins") or "")
    return f"""
    <div class="flight-card {'cheapest' if is_cheapest else ''}">
      <div>{badge}<div class="fc-airline">{row.get('airline','Unknown')}</div><div class="fc-route">{row.get('route','')}</div></div>
      <div style="display:flex;align-items:center;gap:10px">
        <div class="fc-time-block"><div class="fc-time">{dep}</div><div class="fc-tlabel">Dep</div></div>
        <div class="fc-dur">──{dur}──</div>
        <div class="fc-time-block"><div class="fc-time">{arr}</div><div class="fc-tlabel">Arr</div></div>
      </div>
      <div style="text-align:center">{stops_badge(row.get('stops',0))}<div style="font-size:11px;color:#7a8ba0;margin-top:4px">{row.get('flight_date','')}</div></div>
      <div>
        <div class="fc-price-kes">{fmt_kes(row.get('price_kes',0))}</div>
        <div class="fc-price-usd">≈ USD {float(row.get('price_usd',0)):.0f}</div>
        <div style="text-align:right;margin-top:4px">{src_badge(row.get('source',''))}</div>
      </div>
    </div>"""

def run_scraper_thread(route_label=None,flight_date=None):
    st.session_state.scrape_running=True; st.session_state.scrape_status="running"
    st.session_state.scrape_message=f"Scraping {route_label or 'all routes'}…"; st.session_state.scrape_log=""
    env=os.environ.copy()
    if route_label: env["SCRAPE_ROUTE"]=route_label
    if flight_date: env["SCRAPE_DATE"]=str(flight_date)
    try:
        result=subprocess.run([sys.executable,str(SCRAPER)],capture_output=True,text=True,timeout=360,env=env,cwd=str(BASE_DIR))
        st.session_state.scrape_log=(result.stdout or "")[-2000:]
        if result.returncode==0:
            st.session_state.scrape_status="success"; st.session_state.scrape_message="Scrape completed! Data updated."
        else:
            st.session_state.scrape_status="error"; st.session_state.scrape_message=(result.stderr or "No stderr")[-800:]
    except subprocess.TimeoutExpired:
        st.session_state.scrape_status="error"; st.session_state.scrape_message="Scraper timed out after 6 minutes."
    except Exception as e:
        st.session_state.scrape_status="error"; st.session_state.scrape_message=str(e)
    finally:
        st.session_state.scrape_running=False; st.session_state.last_run=time.strftime("%Y-%m-%d %H:%M:%S"); load_data.clear()

with st.sidebar:
    st.markdown("## ✈ Kenya Flights"); st.markdown("---"); st.markdown("### 🔄 Live Scrape")
    scrape_route=st.selectbox("Route to scrape",["All routes"]+list(ROUTES.keys()),key="scrape_route_sel")
    scrape_date=st.date_input("Date",value=date.today(),min_value=date.today(),max_value=date.today()+timedelta(days=30))
    scrape_btn=st.button("▶ Run Scraper",disabled=st.session_state.scrape_running,use_container_width=True,type="primary")
    if scrape_btn and not st.session_state.scrape_running:
        label=None if scrape_route=="All routes" else ROUTES[scrape_route]["label"]
        threading.Thread(target=run_scraper_thread,args=(label,scrape_date),daemon=True).start()
        st.rerun()
    status=st.session_state.scrape_status; msg=st.session_state.scrape_message
    if status=="running": st.markdown(f'<div class="status-running">⚡ {msg}</div>',unsafe_allow_html=True)
    elif status=="success":
        st.markdown(f'<div class="status-success">✓ {msg}</div>',unsafe_allow_html=True)
        if st.session_state.last_run: st.caption(f"Last run: {st.session_state.last_run}")
    elif status=="error":
        st.markdown('<div class="status-error">✗ Scraper error</div>',unsafe_allow_html=True); st.code(msg,language="bash")
    if st.session_state.scrape_log:
        with st.expander("Scraper log"): st.text(st.session_state.scrape_log)
    st.markdown("---"); st.markdown("### 🔍 Filter Flights")
    df_all=load_data()
    route_options=(["All routes"]+sorted(df_all["route"].dropna().unique().tolist())) if not df_all.empty else ["All routes"]
    date_options=(["All dates"]+sorted(df_all["flight_date"].dropna().unique().tolist())) if not df_all.empty else ["All dates"]
    airline_options=(["All airlines"]+sorted([a for a in df_all["airline"].dropna().unique() if a])) if not df_all.empty else ["All airlines"]
    f_route=st.selectbox("Route",route_options); f_date=st.selectbox("Date",date_options)
    f_airline=st.selectbox("Airline",airline_options); f_stops=st.radio("Stops",["Any","Direct only","1 stop"],horizontal=True)
    st.markdown("---"); st.markdown("### ↕ Sort")
    f_sort=st.selectbox("Sort by",["Price (KES)","Departure time","Duration","Stops"])
    f_order=st.radio("Order",["Cheapest first","Most expensive first"])
    sort_map={"Price (KES)":"price_kes","Departure time":"departure_time","Duration":"duration_mins","Stops":"stops"}
    st.markdown("---"); st.markdown("### ⏱ Auto-refresh")
    auto_refresh=st.toggle("Refresh every 30 s",value=st.session_state.auto_refresh)
    st.session_state.auto_refresh=auto_refresh
    if auto_refresh: st.caption("Page will auto-refresh while toggled on.")

df=load_data()
col_title,col_ts=st.columns([3,1])
with col_title:
    st.markdown("# ✈ Kenya Flights"); st.caption("Real-time scraped prices from eSky Kenya")
with col_ts:
    if st.session_state.last_run:
        st.markdown(f"<div style='text-align:right;color:#7a8ba0;font-size:12px;padding-top:20px'>Last updated<br><strong style='color:#e8edf5'>{st.session_state.last_run}</strong></div>",unsafe_allow_html=True)

cheapest_map={}
if not df.empty:
    st.markdown('<div class="section-head">Best prices by route</div>',unsafe_allow_html=True)
    stat_cols=st.columns(len(ROUTES))
    for i,(route_name,meta) in enumerate(ROUTES.items()):
        label=meta["label"]; subset=df[df["route"]==label]
        with stat_cols[i]:
            if not subset.empty:
                best=subset.loc[subset["price_kes"].idxmin()]; cheapest_map[label]=int(best["price_kes"])
                st.metric(label=route_name,value=fmt_kes(best["price_kes"]),delta=f"{best['airline']} · {best['flight_date']}",delta_color="off")
            else: st.metric(label=route_name,value="No data",delta="Run scraper →")
    st.markdown("---")

filtered=df.copy()
if not filtered.empty:
    if f_route!="All routes":   filtered=filtered[filtered["route"]==f_route]
    if f_date!="All dates":     filtered=filtered[filtered["flight_date"]==f_date]
    if f_airline!="All airlines": filtered=filtered[filtered["airline"].str.contains(f_airline,case=False,na=False)]
    if f_stops=="Direct only":  filtered=filtered[filtered["stops"]==0]
    elif f_stops=="1 stop":     filtered=filtered[filtered["stops"]==1]
    filtered=filtered.sort_values(sort_map[f_sort],ascending=(f_order=="Cheapest first"))

res_col,refresh_col=st.columns([2,1])
with res_col:
    total=len(filtered) if not filtered.empty else 0
    st.markdown(f'<div class="section-head">Showing {total} flight{"s" if total!=1 else ""}</div>',unsafe_allow_html=True)
with refresh_col:
    if st.button("↻ Refresh data",use_container_width=True): load_data.clear(); st.rerun()

if filtered.empty:
    if df.empty:
        st.markdown('<div class="empty-state"><div style="font-size:48px;margin-bottom:12px">✈</div><strong style="font-size:18px;color:#e8edf5;font-family:Syne,sans-serif">No flight data yet</strong><p style="margin-top:8px">Click <strong>▶ Run Scraper</strong> in the sidebar.</p></div>',unsafe_allow_html=True)
    else:
        available=df[df["route"]==f_route]["flight_date"].unique() if f_route!="All routes" else []
        hint=f"Available dates for this route: {', '.join(sorted(available))}" if len(available) else "Try adjusting your filters."
        st.markdown(f'<div class="empty-state"><div style="font-size:48px;margin-bottom:12px">🔍</div><strong style="font-size:18px;color:#e8edf5;font-family:Syne,sans-serif">No flights match your filters</strong><p style="margin-top:8px">{hint}</p></div>',unsafe_allow_html=True)
else:
    cards_html=""
    for _,row in filtered.iterrows():
        is_cheapest=row["route"] in cheapest_map and int(row["price_kes"])<=cheapest_map[row["route"]]
        cards_html+=render_flight_card(row.to_dict(),is_cheapest)
    st.markdown(cards_html,unsafe_allow_html=True)

if st.session_state.auto_refresh:
    time.sleep(30); load_data.clear(); st.rerun()
