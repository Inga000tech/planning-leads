import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE FOOLPROOF STARTUP ENGINE ---
# We use 'sys.executable' to ensure we are installing into the EXACT 
# folder Streamlit is currently using.
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Urban Planning Engine: Installing browser..."):
        # This command is the 'magic fix'. It installs Chromium AND 
        # its system dependencies directly into the server's cache.
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"])
        st.session_state.browser_ready = True

from playwright.async_api import async_playwright

st.set_page_config(page_title="Urban Planning Lead Gen", page_icon="🏗️", layout="wide")
st.title("🏗️ Urban Planning Lead Generator")

# --- 2. THE SCRAPER ---
async def fetch_leads(council_name, url, days_back):
    leads = []
    keywords = ["commercial", "retail", "shop", "office", "change of use", "development"]
    async with async_playwright() as p:
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

# --- 3. THE BUTTON ---
if st.button("🚀 Scan Councils Now"):
    all_leads = []
    councils = {"Manchester": "https://pa.manchester.gov.uk", "Westminster": "https://idoxpa.westminster.gov.uk"}
    with st.status("Gathering leads...", expanded=True):
        for name, url in councils.items():
            st.write(f"Scouting {name}...")
            data = asyncio.run(fetch_leads(name, url, 14))
            all_leads.extend(data)
    
    if all_leads:
        st.dataframe(pd.DataFrame(all_leads), use_container_width=True)
    else:
        st.warning("No new leads found.")
