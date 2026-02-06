import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CRITICAL: BROWSER INSTALLER ---
# This block forces the server to install Chromium and its Linux 'bones' (dependencies).
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Setting up Urban Planning Engine... (Wait 60s)"):
        try:
            # We use sys.executable to ensure we use the correct environment
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Error: {e}")

from playwright.async_api import async_playwright

st.set_page_config(page_title="Urban Planning Lead Gen", page_icon="🏗️", layout="wide")
st.title("🏗️ Urban Planning Lead Generator")

# --- 2. THE SCRAPER ENGINE ---
async def fetch_leads(council_name, url, days_back):
    leads = []
    keywords = ["commercial", "retail", "shop", "office", "change of use", "development"]
    
    async with async_playwright() as p:
        # headless=True is mandatory for the cloud server
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(f"{url}/online-applications/search.do?action=advanced", timeout=60000)
            date_str = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
            await page.fill("#applicationValidatedStart", date_str)
            await page.click("input[type='submit'][value='Search']")
            
            results = await page.query_selector_all(".searchresult")
            for res in results:
                text = (await res.inner_text()).lower()
                if any(k in text for k in keywords):
                    link_node = await res.query_selector("a")
                    leads.append({
                        "Council": council_name,
                        "Application": (await res.inner_text()).split('\n')[0],
                        "Link": url + await link_node.get_attribute("href")
                    })
        except Exception as e:
            st.error(f"Error at {council_name}: {e}")
        finally:
            await browser.close()
    return leads

# --- 3. THE ACTION ---
if st.button("🚀 Scan Councils for Leads"):
    all_leads = []
    councils = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status("Gathering leads...", expanded=True) as status:
        for name, url in councils.items():
            st.write(f"Scouting {name}...")
            data = asyncio.run(fetch_leads(name, url, 30))
            all_leads.extend(data)
        status.update(label="Scanning Complete!", state="complete", expanded=False)

    if all_leads:
        st.success(f"Found {len(all_leads)} leads for your startup!")
        st.balloons()
        st.dataframe(pd.DataFrame(all_leads), use_container_width=True)
    else:
        st.warning("No new commercial applications found. Try again tomorrow!")
