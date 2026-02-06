import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE STARTUP ENGINE ---
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Finalizing Urban Planning Engine..."):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Warning: {e}")

from playwright.async_api import async_playwright

# --- 2. THE INTERFACE ---
st.set_page_config(page_title="Urban Planning Lead Gen", page_icon="🏗️", layout="wide")
st.title("🏗️ Urban Planning Lead Generator")
st.markdown("Focused on **Change of Use**, **Prior Approvals**, and **Commercial Conversions**.")

with st.sidebar:
    st.header("Lead Settings")
    days_back = st.slider("Days to look back", 1, 90, 30)
    # Added a 'Sensitivity' setting for your brother
    strict_mode = st.checkbox("Strict Commercial Filter", value=False)
    st.divider()
    st.info("Tip: If you get 0 results, uncheck 'Strict Commercial Filter' to see all recent applications.")

# --- 3. THE IMPROVED SCRAPER ---
async def fetch_leads(council_name, url, days):
    leads = []
    # Broadened keywords for Urban Planning (Prior Approval is huge for startups)
    keywords = [
        "commercial", "retail", "shop", "office", "change of use", 
        "prior approval", "conversion", "annexe", "demolition", "class ma"
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Go to advanced search
            await page.goto(f"{url}/online-applications/search.do?action=advanced", timeout=60000)
            
            # Formulate the date correctly
            start_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
            
            # Fill the 'Date Validated' field
            await page.fill("#applicationValidatedStart", start_date)
            await page.click("input[type='submit'][value='Search']")
            
            # Wait for results to load
            await page.wait_for_selector(".searchresult", timeout=10000)
            
            # Scrape multiple pages (up to 3) to ensure we find something
            for page_num in range(3):
                results = await page.query_selector_all(".searchresult")
                for res in results:
                    raw_text = await res.inner_text()
                    clean_text = raw_text.lower()
                    
                    # Logic: If strict mode is off, take everything. If on, filter by keywords.
                    if not strict_mode or any(k in clean_text for k in keywords):
                        header = await res.query_selector("a")
                        title = await header.inner_text()
                        link = await header.get_attribute("href")
                        
                        leads.append({
                            "Council": council_name,
                            "Description": title.strip(),
                            "Link": url + link,
                            "Match Type": "Keyword Match" if any(k in clean_text for k in keywords) else "Recent App"
                        })
                
                # Try to click 'Next'
                next_btn = await page.query_selector("a.next")
                if next_btn:
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                else:
                    break
                    
        except Exception as e:
            st.warning(f"Note: {council_name} search returned no results or timed out. They may have no new validated apps today.")
        finally:
            await browser.close()
    return leads

# --- 4. THE ACTION ---
if st.button("🚀 Run Lead Scout"):
    all_leads = []
    councils = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status("Scanning Council Portals...", expanded=True) as status:
        for name, url in councils.items():
            st.write(f"Checking {name} for new planning files...")
            data = asyncio.run(fetch_leads(name, url, days_back))
            all_leads.extend(data)
        status.update(label="Scan Complete!", state="complete", expanded=False)

    if all_leads:
        df = pd.DataFrame(all_leads)
        
        # Sort so keyword matches appear at the top
        df = df.sort_values(by="Match Type", ascending=False)
        
        st.success(f"Found {len(df)} potential opportunities!")
        st.balloons()
        
        # Display results with clickable links
        st.dataframe(
            df, 
            column_config={
                "Link": st.column_config.LinkColumn("View on Council Site")
            },
            use_container_width=True,
            hide_index=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Save Leads to CSV", csv, "urban_planning_leads.csv", "text/csv")
    else:
        st.error("No leads found. Council websites might be blocking the connection or the date range is too small.")
        st.info("Try unchecking 'Strict Commercial Filter' in the sidebar to see all recent activity.")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Lead Scout")
