import streamlit as st
import asyncio
import os
import pandas as pd
from playwright.async_api import async_playwright
from datetime import datetime, timedelta

# --- 1. ROBUST CLOUD INSTALLER ---
# This fixes the "Executable doesn't exist" error by forcing the install 
# of both the browser and its system dependencies on the server.
if "browser_ready" not in st.session_state:
    with st.spinner("Preparing Lead Engine... (This takes 30-60s on the first run)"):
        os.system("python -m playwright install chromium --with-deps")
        st.session_state.browser_ready = True

# --- 2. USER FRIENDLY UI SETUP ---
st.set_page_config(page_title="Planning Lead Pro", page_icon="🏢", layout="wide")

# Custom Styling for Mark
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏢 Planning Lead Pro")
st.subheader("Automated Lead Sourcing for Manchester & Westminster")

# Sidebar for simple controls
with st.sidebar:
    st.header("Search Settings")
    days_to_look = st.slider("Look back (Days)", 1, 60, 14, help="How many days of history to scan.")
    st.divider()
    st.info("Hi Mark! Click the blue button on the right to start scanning for new leads.")

# --- 3. THE SCRAPER LOGIC ---
async def scrape_council(council_name, base_url, days):
    results = []
    # Commercial-focused keywords
    keywords = ["retail", "shop", "office", "commercial", "restaurant", "change of use", "leisure"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to Advanced Search
            await page.goto(f"{base_url}/online-applications/search.do?action=advanced", timeout=60000)
            
            # Fill in the date
            target_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
            await page.fill("#applicationValidatedStart", target_date)
            await page.click("input[type='submit'][value='Search']")
            
            # Scan results
            rows = await page.query_selector_all(".searchresult")
            for row in rows:
                text = (await row.inner_text()).lower()
                if any(k in text for k in keywords):
                    link_el = await row.query_selector("a")
                    results.append({
                        "Council": council_name,
                        "Summary": (await row.inner_text()).split('\n')[0],
                        "Link": base_url + await link_el.get_attribute("href")
                    })
        except Exception as e:
            st.error(f"Error connecting to {council_name}. They might be down for maintenance.")
        finally:
            await browser.close()
    return results

# --- 4. THE ACTION ---
if st.button("🚀 Find New Leads Now"):
    all_data = []
    targets = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status("Scraping Council Databases...", expanded=True) as status:
        for name, url in targets.items():
            st.write(f"Scanning {name}...")
            data = asyncio.run(scrape_council(name, url, days_to_look))
            all_data.extend(data)
        status.update(label="Scanning Complete!", state="complete", expanded=False)

    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"Found {len(df)} potential commercial leads!")
        st.balloons()
        
        # Display as a clean table
        st.dataframe(df, use_container_width=True)
        
        # Easy download for Mark
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Leads as CSV", csv, "planning_leads.csv", "text/csv")
    else:
        st.warning("No commercial leads found in that timeframe. Try a longer 'Look back' in the sidebar.")
