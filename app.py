import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. ENGINE INITIALIZATION ---
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Calibrating Lead Engine..."):
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
    weeks_to_scan = st.slider("Weeks to look back", 1, 8, 4)
    st.divider()
    st.info("Tailored for Urban Planning Startups.")

# --- 2. THE SMART SCRAPER ---
async def scrape_manchester_smart(weeks):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail", "shop", "restaurant"]
    base_url = "https://pa.manchester.gov.uk/online-applications"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # STEP 1: Handshake
            st.write("🔑 Priming Security Session...")
            await page.goto(f"{base_url}/main.do?action=terms", timeout=60000)
            
            accept_selector = 'input[type="submit"][value*="Accept"], input[name="agree"]'
            if await page.query_selector(accept_selector):
                st.write("🔓 Unlocking Portal...")
                await page.click(accept_selector)
                await page.wait_for_load_state("networkidle")
            
            # STEP 2: Navigate to Weekly List
            st.write("📅 Accessing Weekly Register...")
            await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)
            
            # STEP 3: Handle the "Validated" Selection (Fixed for Radio Buttons)
            # We wait for EITHER a dropdown (#weeklyListDisplayType) OR radio buttons (input[value='validated'])
            await page.wait_for_selector("#weeklyListDisplayType, input[value='validated']", timeout=30000)
            
            if await page.query_selector("input[value='validated']"):
                await page.click("input[value='validated']") # Manchester uses this radio button
            elif await page.query_selector("#weeklyListDisplayType"):
                await page.select_option("#weeklyListDisplayType", "validated")

            # STEP 4: Loop through weeks
            # We fetch options for the '#week' dropdown
            options_elements = await page.query_selector_all("#week option")
            week_values = []
            for i in range(min(len(options_elements), weeks)):
                val = await options_elements[i].get_attribute("value")
                txt = await options_elements[i].inner_text()
                week_values.append((val, txt))

            for val, txt in week_values:
                st.write(f"🔍 Scanning Week: **{txt}**")
                await page.select_option("#week", val)
                
                # Click Search and wait for navigation
                await asyncio.gather(
                    page.wait_for_navigation(),
                    page.click('input[type="submit"][value="Search"]')
                )
                
                # Scrape results
                results = await page.query_selector_all(".searchresult")
                for res in results:
                    content = (await res.inner_text()).lower()
                    if any(k in content for k in keywords):
                        link_node = await res.query_selector("a")
                        title = await link_node.inner_text()
                        href = await link_node.get_attribute("href")
                        all_leads.append({
                            "Week": txt,
                            "Project": title.strip(),
                            "Type": "PRIORITY" if "prior approval" in content else "Standard",
                            "Link": "https://pa.manchester.gov.uk" + href
                        })
                
                # Go back to search setup
                await page.goto(f"{base_url}/search.do?action=weeklyList")
                await page.wait_for_load_state("networkidle")

        except Exception as e:
            st.error(f"Scraper Error: {str(e)[:150]}")
            # Show a screenshot for the user to confirm the UI state
            await page.screenshot(path="debug.png")
            st.image("debug.png", caption="Current Portal State")
        finally:
            await browser.close()
    return all_leads

# --- 3. THE ACTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    if target_council == "Manchester":
        with st.status("Searching Manchester...", expanded=True):
            leads = asyncio.run(scrape_manchester_smart(weeks_to_scan))
        
        if leads:
            df = pd.DataFrame(leads)
            st.success(f"Found {len(df)} High-Value Leads!")
            st.balloons()
            st.dataframe(df, column_config={"Link": st.column_config.LinkColumn("View Case")}, use_container_width=True, hide_index=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8'), "leads.csv")
        else:
            st.warning("No commercial leads found. Try a different date range.")

    elif target_council == "Westminster":
        st.error("🚨 Westminster Portal is currently offline due to a cyber-attack.")
        st.link_button("Go to Westminster Temporary Manual List", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Lead Scout | Barcelona, Spain")
