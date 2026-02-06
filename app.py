import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Planning Lead Scout", page_icon="🏢", layout="wide")

# Custom CSS for a professional "SaaS" look
st.markdown("""
    <style>
    .stDataFrame { border-radius: 10px; }
    .stRadio > label { font-weight: bold; color: #1f77b4; }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏢 Urban Planning Lead Scout")
st.subheader("Targeting Prior Approvals & Appeals (London Focus)")

# --- 2. SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🎯 Lead Targeting")
    view_mode = st.radio(
        "Filter by Result:", 
        ["All Leads", "Refused (Appeals Strategy)", "Approved (Development Ready)"]
    )
    
    days_back = st.slider("Look back (days):", 1, 30, 14)
    
    st.divider()
    st.info("💡 **Strategy:** Focus on 'Refused' Prior Approvals. These are the developers most likely to hire a consultant for an appeal.")

# --- 3. THE LEAD ENGINE (Simulated London Datahub Feed) ---
def fetch_leads(days, mode):
    # This simulates the 2026 London Planning Datahub live feed
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
    
    # Filter by Status
    if mode == "Refused (Appeals Strategy)":
        df = df[df['Status'] == "Refused"]
    elif mode == "Approved (Development Ready)":
        df = df[df['Status'] == "Approved"]
    
    # Create the Research Link for finding emails/LinkedIn
    df['Contact Research'] = df['Applicant'].apply(
        lambda x: f"https://www.google.com/search?q={x.replace(' ', '+')}+UK+company+contact+LinkedIn"
    )
    
    return df

# --- 4. DISPLAY ---
leads_df = fetch_leads(days_back, view_mode)

if not leads_df.empty:
    st.write(f"Showing **{len(leads_df)}** qualified leads found.")

    # Highlighting Status
    def style_status(val):
        color = '#d9534f' if val == 'Refused' else '#5cb85c'
        return f'background-color: {color}; color: white; font-weight: bold; border-radius: 5px;'

    st.dataframe(
        leads_df.style.applymap(style_status, subset=['Status']),
        column_config={
            "Contact Research": st.column_config.LinkColumn("🔍 Find Email/LinkedIn"),
            "Date": st.column_config.DateColumn("Date Received"),
            "Description": st.column_config.TextColumn("Project Details", width="large")
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.download_button(
        label="📥 Export Lead List (CSV)",
        data=leads_df.to_csv(index=False).encode('utf-8'),
        file_name="urban_planning_leads.csv",
        mime="text/csv"
    )
else:
    st.warning("No leads found for this period. Try expanding the date range.")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Lead Scout | Barcelona-London Pipeline")
