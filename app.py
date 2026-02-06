import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE FOOLPROOF STARTUP ENGINE ---
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Urban Planning Engine: Installing browser..."):
        # We use sys.executable to find the correct Python environment
        # and subprocess.run for better error handling than os.system
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"])
        st.session_state.browser_ready = True

from playwright.async_api import async_playwright
# ... the rest of your app logic remains the same ...

# --- 2. USER INTERFACE ---
st.set_page_config(page_title="Planning Lead Pro", page_icon="🏢", layout="wide")

# Custom branding for Mark
st.title("🏢 Planning Lead Pro")
st.markdown("Automated lead sourcing for **Manchester** and **Westminster** councils.")

with st.sidebar:
    st.header("Search Settings")
    days_back = st.slider("Days to look back", 1, 90, 14)
    search_depth = st.number_input("Max Pages to Scan", 1, 10, 3)
    st.divider()
    st.info("Mark: Click the blue button below to fetch today's commercial leads.")

# --- 3. THE SCRAPER ENGINE ---
async def scrape_council(council_name, base_url, days, pages):
    leads = []
    # Commercial keywords to filter the noise
    keywords = ["retail", "shop", "commercial", "office", "restaurant", "change of use"]
    
    async with async_playwright() as p:
        # Launching headless is required for Streamlit Cloud
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to Advanced Search
            search_url = f"{base_url}/online-applications/search.do?action=advanced"
            await page.goto(search_url, timeout=60000)
            
            # Fill in the 'Validated Date'
            start_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
            await page.fill("#applicationValidatedStart", start_date)
            await page.click("input[type='submit'][value='Search']")
            
            # Simple loop to check result pages
            for _ in range(pages):
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
                
                # Check for 'Next' button
                next_page = await page.query_selector("a.next")
                if next_page:
                    await next_page.click()
                    await page.wait_for_load_state("networkidle")
                else:
                    break
        except Exception as e:
            st.error(f"Error scanning {council_name}: {str(e)}")
        finally:
            await browser.close()
    return leads

# --- 4. ACTION BUTTON ---
if st.button("🚀 Start Lead Generation"):
    all_leads = []
    targets = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status("Searching Databases...", expanded=True) as status:
        for name, url in targets.items():
            st.write(f"🔍 Scanning {name} Council...")
            results = asyncio.run(scrape_council(name, url, days_back, search_depth))
            all_leads.extend(results)
        status.update(label="Scanning Complete!", state="complete")
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        st.success(f"Found {len(df)} potential leads!")
        st.balloons()
        st.dataframe(df, use_container_width=True)
        
        # Download button for Mark
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Results (CSV)", csv, f"leads_{datetime.now().date()}.csv", "text/csv")
    else:
        st.warning("No commercial leads found. Try a longer 'Look back' or more pages.")

st.divider()
st.caption("Securely hosted on Streamlit Cloud 2026. Safe for all devices.")
