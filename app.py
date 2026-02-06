import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE ENGINE ---
if "browser_ready" not in st.session_state:
    with st.spinner("🕵️ Calibrating Stealth Engine..."):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Error: {e}")

from playwright.async_api import async_playwright

st.set_page_config(page_title="Urban Planning Lead Scout", page_icon="🏢", layout="wide")
st.title("🏢 Urban Planning Lead Scout")

with st.sidebar:
    st.header("Search Parameters")
    target_council = st.selectbox("Select Council", ["Manchester", "Westminster"])
    weeks_to_scan = st.slider("Weeks to scan", 1, 8, 4)
    st.divider()
    st.info("Directly for Urban Planning Startups.")

# --- 2. THE ULTIMATE SCRAPER ---
async def scrape_manchester_final(weeks):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail"]
    base_url = "https://pa.manchester.gov.uk/online-applications"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Persistent context to keep cookies/session alive
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        try:
            # STEP 1: Go to the Weekly List page directly
            st.write("🔗 Connecting to Manchester...")
            await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)
            
            # STEP 2: Check for Disclaimer/Terms
            # We look for the "Accept" button. If it's there, we click it.
            accept_btn = await page.query_selector('input[value="I Accept"], input[name="agree"], .button.primary')
            if accept_btn:
                st.write("🔓 Clearing Security Wall...")
                await accept_btn.click()
                # CRITICAL: Wait for the page to reload with the search form
                await page.wait_for_load_state("networkidle")
            
            # STEP 3: Ensure we are on the search page
            # If the server redirected us away, go back to Weekly List (the cookie is now set)
            if not await page.query_selector("#weeklyListDisplayType"):
                await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)

            # STEP 4: Select 'Validated' apps
            st.write("📅 Accessing Weekly Register...")
            await page.wait_for_selector("#weeklyListDisplayType", timeout=30000)
            await page.select_option("#weeklyListDisplayType", "validated")
            
            # STEP 5: Loop through weeks
            options = await page.query_selector_all("#week option")
            for i in range(min(len(options), weeks)):
                # Refresh options list
                current_options = await page.query_selector_all("#week option")
                week_val = await current_options[i].get_attribute("value")
                week_text = await current_options[i].inner_text()
                
                st.write(f"🔍 Scanning: {week_text}")
                await page.select_option("#week", week_val)
                # Use wait_for_navigation to ensure the results page loads
                async with page.expect_navigation():
                    await page.click('input[type="submit"]')
                
                # Scrape results
                results = await page.query_selector_all(".searchresult")
                for res in results:
                    text = (await res.inner_text()).lower()
                    if any(k in text for k in keywords):
                        link_el = await res.query_selector("a")
                        title = await link_el.inner_text()
                        href = await link_el.get_attribute("href")
                        all_leads.append({
                            "Date": week_text,
                            "Project": title.strip(),
                            "Type": "PRIORITY" if "prior approval" in text else "Commercial",
                            "Link": "https://pa.manchester.gov.uk" + href
                        })
                
                # Go back to the search page for the next week
                await page.goto(f"{base_url}/search.do?action=weeklyList")
                await page.wait_for_selector("#week")

        except Exception as e:
            st.error(f"Technical Glitch: {e}")
        finally:
            await browser.close()
    return all_leads

# --- 3. THE ACTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    if target_council == "Manchester":
        with st.status("Searching Manchester...", expanded=True):
            leads = asyncio.run(scrape_manchester_final(weeks_to_scan))
        
        if leads:
            df = pd.DataFrame(leads)
            st.success(f"Found {len(df)} Leads!")
            st.dataframe(df, column_config={"Link": st.column_config.LinkColumn("View")}, use_container_width=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8'), "leads.csv")
        else:
            st.warning("No commercial leads found. The keywords might be too strict.")

    elif target_council == "Westminster":
        st.error("🚨 Westminster Portal is currently offline due to a cyber-attack.")
        st.link_button("Go to Westminster Temporary Manual List", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Status | Barcelona, Spain")
