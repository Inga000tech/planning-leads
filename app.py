import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Urban Planning Lead Scout", page_icon="🏢", layout="wide")

# Custom CSS to make the 'Refused' status pop
st.markdown("""
    <style>
    .reportview-container { background: #f0f2f6; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF; color: white; }
    </style>
    """, unsafe_allow_name_ যথানির্দেশিত)

st.title("🏢 Urban Planning Lead Scout")
st.markdown("### Focus: London Prior Approvals & Appeals")

# --- 1. SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🎯 Lead Targeting")
    view_mode = st.radio(
        "Filter by Result:", 
        ["All Leads", "Refused (Appeals Strategy)", "Approved (Development Ready)"]
    )
    
    days_back = st.slider("Look back (days):", 1, 30, 14)
    
    st.divider()
    st.markdown("""
    **Search Keywords:**
    * Prior Approval (Class MA)
    * Change of Use
    * Commercial to Residential
    """)
    st.info("Current Focus: Southwark & London Hub (Highest Reliability)")

# --- 2. THE LEAD ENGINE ---
# This function simulates the data coming from the London Hub API 
# which is much more stable than the Manchester portal.
def fetch_london_leads(days, mode):
    # Mocking the live API response structure
    raw_data = [
        {"Date": "2026-02-05", "Address": "12 Camberwell Road, SE5", "Type": "Prior Approval (Class MA)", "Status": "Refused", "Applicant": "Goldstar Assets Ltd", "Description": "Change of use from Office to 6 self-contained flats."},
        {"Date": "2026-02-04", "Address": "The Old Printworks, SE1", "Type": "Change of Use", "Status": "Refused", "Applicant": "Riverview Developments", "Description": "Conversion of light industrial unit to 4 creative studios."},
        {"Date": "2026-02-03", "Address": "99 Borough High St, SE1", "Type": "Prior Approval", "Status": "Approved", "Applicant": "High Street Holdings", "Description": "Shop to residential conversion."},
        {"Date": "2026-02-02", "Address": "Unit 4, Peckham Business Park", "Type": "Prior Approval", "Status": "Refused", "Applicant": "Skyline Ventures", "Description": "Office to 12 apartments."},
        {"Date": "2026-02-01", "Address": "22 Lordship Lane, SE22", "Type": "Change of Use", "Status": "Approved", "Applicant": "Private Developer", "Description": "Retail to Restaurant with flat above."},
    ]
    
    df = pd.DataFrame(raw_data)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Filter by date
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df['Date'] >= cutoff]
    
    # Filter by Status (Mark's Strategy)
    if mode == "Refused (Appeals Strategy)":
        df = df[df['Status'] == "Refused"]
    elif mode == "Approved (Development Ready)":
        df = df[df['Status'] == "Approved"]
    
    # Add Google Search Helper Column
    df['Contact Research'] = df['Applicant'].apply(lambda x: f"https://www.google.com/search?q={x.replace(' ', '+')}+UK+company+contact")
    
    return df

# --- 3. DISPLAY & INTERACTION ---
leads = fetch_london_leads(days_back, view_mode)

col1, col2 = st.columns([4, 1])
with col1:
    st.write(f"Showing **{len(leads)}** leads found in the last {days_back} days.")

if not leads.empty:
    # Stylized Table
    def style_status(val):
        color = '#d9534f' if val == 'Refused' else '#5cb85c'
        return f'background-color: {color}; color: white; font-weight: bold; border-radius: 5px;'

    st.dataframe(
        leads.style.applymap(style_status, subset=['Status']),
        column_config={
            "Contact Research": st.column_config.LinkColumn("🔍 Find Email/LinkedIn"),
            "Date": st.column_config.DateColumn("Received")
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.download_button(
        label="📥 Export Lead List (CSV)",
        data=leads.to_csv(index=False).encode('utf-8'),
        file_name=f"planning_leads_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
else:
    st.warning("No leads found for this period. Try increasing the 'Look back' slider.")

st.divider()
st.caption("Barcelona-London Urban Planning Pipeline | MVP v1.1")
