import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE STABLE STARTUP ENGINE ---
# We removed '--with-deps' because it causes a crash on Streamlit Cloud.
# 'packages.txt' handles the dependencies instead.
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Urban Planning Engine: Finalizing setup..."):
        try:
            # Install only the browser engine. 
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Warning: {e}. The app will still attempt to run.")

from playwright.async_api import async_playwright

# --- 2. USER INTERFACE ---
st.set_page_config(page_title="Urban Planning Lead Gen", page_icon="🏗️", layout="wide")
st.title("🏗️ Urban Planning Lead Generator")
st.markdown("Automated lead sourcing for **Manchester** and **Westminster** councils.")

with st.sidebar:
    st.header("Search Settings")
    days_back = st.slider("Days to look back", 1, 90, 30)
    st.divider()
    st.info("Hi! Click the button below to start the scan for your startup.")

# --- 3. THE SCRAPER ENGINE ---
async def scrape_council(council_name, base_url, days):
    leads = []
    # Keywords focused on Urban Planning opportunities
    keywords = ["commercial", "retail", "shop", "office", "change of use", "development", "prior approval"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to Advanced Search
            search_url = f"{base_url}/online-applications/search.do?action=advanced"
            await page.goto(search_url, timeout=60000)
            
            # Fill in the date
            start_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
            await page.fill("#applicationValidatedStart", start_date)
            await page.click("input[type='submit'][value='Search']")
            
            # Scan results (First page)
            results = await page.query_selector_all(".searchresult")
            for res in results:
                text = (await res.inner_text()).lower()
                if any(k in text for k in keywords):
                    header = await res.query_selector("a")
                    title = await header.inner_text()
                    link = await header.get_attribute("href")
                    leads.append({
                        "Council": council_name,
                        "Title": title.strip(),
                        "Link": base_url + link
                    })
        except Exception as e:
            st.error(f"Error at {council_name}: {str(e)}")
        finally:
            await browser.close()
    return leads

# --- 4. ACTION BUTTON ---
if st.button("🚀 Scan Councils Now"):
    all_leads = []
    targets = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status("Gathering new planning applications...", expanded=True) as status:
        for name, url in targets.items():
            st.write(f"Scouting {name} Council...")
            # Use a new event loop for the async function
            results = asyncio.run(scrape_council(name, url, days_back))
            all_leads.extend(results)
        status.update(label="Scanning Complete!", state="complete", expanded=False)
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        st.success(f"Found {len(df)} potential commercial opportunities!")
        st.balloons()
        st.dataframe(df, use_container_width=True)
        
        # Download for the startup records
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Leads to CSV", csv, "leads.csv", "text/csv")
    else:
        st.warning("No commercial leads found. Try a longer 'Look back' in the sidebar.")

st.divider()
st.caption("Securely hosted for Urban Planning Startup. 2026 Live Status | Barcelona, Spain.")
