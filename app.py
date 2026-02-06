import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE STEALTH ENGINE ---
if "browser_ready" not in st.session_state:
    with st.spinner("🕵️ Opening Urban Planning Lead Scout..."):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Error: {e}")

from playwright.async_api import async_playwright

st.set_page_config(page_title="Urban Planning Lead Scout", page_icon="🏢", layout="wide")

# --- 2. THE STARTUP DASHBOARD ---
st.title("🏢 Urban Planning Lead Scout")
st.markdown("Automated lead sourcing for **Manchester** and **Westminster** Councils.")

with st.sidebar:
    st.header("Lead Settings")
    target_council = st.selectbox("Select Target Council", ["Manchester", "Westminster"])
    weeks_to_scan = st.slider("Weeks to scan", 1, 8, 2)
    st.divider()
    if target_council == "Westminster":
        st.warning("⚠️ **Alert:** Westminster is currently using manual lists due to a recent cyber incident.")
    st.info("This tool targets **Prior Approvals** and **Commercial-to-Residential** leads.")

# --- 3. THE "HANDSHAKE" SCRAPER ---
async def scrape_manchester(base_url, weeks):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a real browser signature to avoid being blocked
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        try:
            # STEP 1: The "Handshake" - Visit the Terms page first to set the cookie
            st.write("🔓 Clearing Security Wall...")
            await page.goto(f"{base_url}/online-applications/main.do?action=terms", timeout=60000)
            
            # Click the 'Accept' button (handles multiple variations)
            accept_button = await page.query_selector('input[type="submit"][value*="Accept"], input[name="agree"]')
            if accept_button:
                await accept_button.click()
                await page.wait_for_load_state("networkidle")

            # STEP 2: Navigate to Weekly List
            st.write("📅 Accessing Weekly Register...")
            await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList", timeout=60000)
            
            # Select 'Validated' apps
            await page.wait_for_selector("#weeklyListDisplayType", timeout=30000)
            await page.select_option("#weeklyListDisplayType", "validated")
            
            # STEP 3: Loop through weeks
            options = await page.query_selector_all("#week option")
            for i in range(min(len(options), weeks)):
                # Refresh options
                current_options = await page.query_selector_all("#week option")
                week_val = await current_options[i].get_attribute("value")
                week_text = await current_options[i].inner_text()
                
                st.write(f"🔍 Scanning Week: {week_text}")
                await page.select_option("#week", week_val)
                await page.click('input[type="submit"]')
                
                # Wait for result table
                try:
                    await page.wait_for_selector(".searchresult", timeout=10000)
                    results = await page.query_selector_all(".searchresult")
                    for res in results:
                        text = (await res.inner_text()).lower()
                        if any(k in text for k in keywords):
                            link_node = await res.query_selector("a")
                            title = await link_node.inner_text()
                            href = await link_node.get_attribute("href")
                            all_leads.append({
                                "Council": "Manchester",
                                "Date": week_text,
                                "Project": title.strip(),
                                "Type": "PRIORITY" if "prior approval" in text else "Commercial",
                                "Link": base_url + href
                            })
                    # Go back for next week
                    await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList")
                except:
                    await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList")
                    continue
                    
        except Exception as e:
            st.error(f"Technical Glitch: {e}")
        finally:
            await browser.close()
    return all_leads

# --- 4. EXECUTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    if target_council == "Manchester":
        with st.status("Scanning Manchester...", expanded=True) as status:
            leads = asyncio.run(scrape_manchester("https://pa.manchester.gov.uk", weeks_to_scan))
            status.update(label="Scout Complete!", state="complete")
        
        if leads:
            df = pd.DataFrame(leads)
            st.success(f"Found {len(df)} High-Value Leads!")
            st.balloons()
            st.dataframe(df, column_config={"Link": st.column_config.LinkColumn("View Case")}, use_container_width=True, hide_index=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8'), "manchester_leads.csv")
        else:
            st.warning("No new commercial matches found in Manchester for this period.")

    elif target_council == "Westminster":
        st.error("🚨 **System Offline:** Westminster's portal is currently down due to a cyber incident.")
        st.markdown("""
        ### How to get leads for Westminster right now:
        Westminster is publishing **manual Excel lists** while they repair their systems. 
        1. Visit their [Temporary Register Page](https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications)
        2. Download the latest **XLSX file** (Temporary Planning Register).
        3. Search for "Prior Approval" or "Change of Use" inside that Excel file.
        """)
        st.link_button("Go to Westminster Temporary List", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Lead Scout | Barcelona, Spain.")
