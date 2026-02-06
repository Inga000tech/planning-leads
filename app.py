import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE STEALTH ENGINE ---
if "browser_ready" not in st.session_state:
    with st.spinner("🕵️ Setting up Stealth Lead Scout..."):
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
    st.header("Lead Parameters")
    target_council = st.selectbox("Select Target Council", ["Manchester", "Westminster"])
    lookback_weeks = st.slider("Weeks to scan", 1, 12, 4)
    st.divider()
    st.info("This tool targets **Prior Approvals** and **Commercial-to-Residential** leads.")

# --- 3. THE PROFESSIONAL SCRAPER ---
async def scrape_weekly_list(council_name, base_url, weeks):
    all_found = []
    # Keywords that represent high-value leads for an Urban Planner
    high_value_keywords = ["prior approval", "change of use", "conversion", "commercial", "office", "retail", "class ma"]
    
    async with async_playwright() as p:
        # User-Agent makes the scraper look like a real person in Barcelona/London
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Step 1: Navigate to Weekly List
            st.write(f"🔍 Accessing {council_name} Weekly Register...")
            await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList", timeout=60000)
            
            # Step 2: Select 'Validated' applications (The "Hot" Leads)
            await page.select_option("#weeklyListDisplayType", "validated")
            
            # Step 3: Iterate through weeks
            # We look at the last 'X' options in the dropdown
            options = await page.query_selector_all("#week option")
            for i in range(min(len(options), weeks)):
                # Re-fetch options to avoid 'stale' elements
                current_options = await page.query_selector_all("#week option")
                val = await current_options[i].get_attribute("value")
                text = await current_options[i].inner_text()
                
                st.write(f"📁 Checking week: {text}")
                await page.select_option("#week", val)
                await page.click("input[type='submit']")
                
                # Wait for results or 'No results' message
                try:
                    await page.wait_for_selector(".searchresult", timeout=5000)
                    results = await page.query_selector_all(".searchresult")
                    
                    for res in results:
                        raw_text = (await res.inner_text()).lower()
                        
                        # Filter for high-value Urban Planning terms
                        if any(k in raw_text for k in high_value_keywords):
                            link_node = await res.query_selector("a")
                            title = await link_node.inner_text()
                            href = await link_node.get_attribute("href")
                            
                            all_found.append({
                                "Council": council_name,
                                "Week": text,
                                "Project": title.strip(),
                                "Type": "High Priority" if "prior approval" in raw_text else "General Commercial",
                                "Link": base_url + href
                            })
                    # Go back to the search page to select the next week
                    await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList")
                except:
                    # No results for this specific week, move to next
                    await page.goto(f"{base_url}/online-applications/search.do?action=weeklyList")
                    continue
                    
        except Exception as e:
            st.error(f"Scraper Error: {e}")
        finally:
            await browser.close()
    return all_found

# --- 4. EXECUTION ---
if st.button(f"🚀 Scout {target_council} Leads"):
    councils = {
        "Manchester": "https://pa.manchester.gov.uk",
        "Westminster": "https://idoxpa.westminster.gov.uk"
    }
    
    with st.status(f"Scanning {target_council}...", expanded=True) as status:
        leads = asyncio.run(scrape_weekly_list(target_council, councils[target_council], lookback_weeks))
        status.update(label="Scouting Complete!", state="complete")

    if leads:
        df = pd.DataFrame(leads)
        st.success(f"Success! Found {len(df)} qualified leads for the startup.")
        st.balloons()
        
        # Professional formatting
        st.dataframe(
            df, 
            column_config={"Link": st.column_config.LinkColumn("View Case File")},
            use_container_width=True,
            hide_index=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Lead List (CSV)", csv, f"{target_council}_leads.csv", "text/csv")
    else:
        st.error("Still no results found.")
        st.info("Check if the Council website is currently down. Westminster has had recent maintenance issues.")
