import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. ENGINE INITIALIZATION ---
if "browser_ready" not in st.session_state:
    with st.spinner("🕵️ Opening Council Portals..."):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Error: {e}")

from playwright.async_api import async_playwright

st.set_page_config(page_title="Urban Planning Lead Scout", page_icon="🏢", layout="wide")

# --- 2. THE DASHBOARD ---
st.title("🏢 Urban Planning Lead Scout")
st.markdown("Automated lead sourcing for **Manchester** and **Westminster** Councils.")

with st.sidebar:
    st.header("Search Parameters")
    target_council = st.selectbox("Select Council", ["Manchester", "Westminster"])
    weeks_to_scan = st.slider("Weeks to look back", 1, 8, 2)
    st.divider()
    st.info("Note: Westminster is currently recovering from a system update; some links may be slow.")

# --- 3. THE "DOOR OPENER" SCRAPER ---
async def scrape_council_pro(council_name, base_url, weeks):
    all_leads = []
    # High-value keywords for Urban Planning startups
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Stealth mode to bypass bot detection
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()
        
        try:
            # STEP 1: Land on the Weekly List page
            st.write(f"🔗 Connecting to {council_name} register...")
            await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList", timeout=90000)
            
            # STEP 2: Handle the "Disclaimer/Terms" Wall
            # This is why the previous script timed out
            if await page.query_selector('input[value="I Accept"]') or await page.query_selector('input[name="agree"]'):
                st.write("🔓 Accepting Terms & Conditions...")
                await page.click('input[value="I Accept"], input[name="agree"]')
                await page.wait_for_load_state("networkidle")

            # STEP 3: Load the Weekly List
            await page.wait_for_selector("#weeklyListDisplayType", timeout=60000)
            await page.select_option("#weeklyListDisplayType", "validated")
            
            # STEP 4: Loop through the weeks
            options = await page.query_selector_all("#week option")
            for i in range(min(len(options), weeks)):
                # Refresh options list
                current_options = await page.query_selector_all("#week option")
                week_val = await current_options[i].get_attribute("value")
                week_text = await current_options[i].inner_text()
                
                st.write(f"📅 Checking week: {week_text}")
                await page.select_option("#week", week_val)
                await page.click("input[type='submit']")
                
                # Scan the results
                try:
                    await page.wait_for_selector(".searchresult", timeout=10000)
                    results = await page.query_selector_all(".searchresult")
                    for res in results:
                        text = (await res.inner_text()).lower()
                        if any(k in text for k in keywords):
                            link_el = await res.query_selector("a")
                            title = await link_el.inner_text()
                            href = await link_el.get_attribute("href")
                            
                            all_leads.append({
                                "Week": week_text,
                                "Project": title.strip(),
                                "Category": "PRIORITY" if "prior approval" in text else "Commercial",
                                "Link": base_url + href
                            })
                    # Go back to search page to select next week
                    await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList")
                except:
                    # No results for this specific week
                    await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList")
                    continue

        except Exception as e:
            st.error(f"Technical Glitch: {str(e)[:150]}...")
            st.info("The council site might be undergoing maintenance. Try again in 10 minutes.")
        finally:
            await browser.close()
    return all_leads

# --- 4. RUN ACTION ---
if st.button(f"🚀 Scout {target_council} for Leads"):
    councils = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status(f"Scanning {target_council}...", expanded=True) as status:
        leads = asyncio.run(scrape_council_pro(target_council, councils[target_council], weeks_to_scan))
        status.update(label="Scanning Finished!", state="complete")

    if leads:
        df = pd.DataFrame(leads)
        st.success(f"Found {len(df)} Qualified Leads!")
        st.balloons()
        st.dataframe(df, column_config={"Link": st.column_config.LinkColumn("Open Case File")}, use_container_width=True, hide_index=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Save Leads as CSV", csv, f"leads_{target_council}.csv", "text/csv")
    else:
        st.warning("No commercial leads found for this period. Try increasing the look-back window.")
