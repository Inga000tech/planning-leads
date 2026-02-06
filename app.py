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
    weeks_to_scan = st.slider("Weeks to look back", 1, 8, 2)
    st.divider()
    include_validated = st.checkbox("Scan Validated (New)", value=True)
    include_decided = st.checkbox("Scan Decided (Closed/Approved)", value=True)
    st.info("Tailored for Urban Planning Startups.")

# --- 2. THE MULTI-STAGE SCRAPER ---
async def scrape_manchester_comprehensive(weeks, scan_types):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail", "shop", "restaurant"]
    base_url = "https://pa.manchester.gov.uk/online-applications"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        try:
            # STEP 1: Handshake
            await page.goto(f"{base_url}/main.do?action=terms", timeout=60000)
            accept_btn = await page.query_selector('input[type="submit"][value*="Accept"], input[name="agree"]')
            if accept_btn:
                await accept_btn.click()
                await page.wait_for_load_state("networkidle")
            
            # STEP 2: Iterate through types (Validated/Decided)
            for scan_type in scan_types:
                st.write(f"📂 Preparing **{scan_type.capitalize()}** scan...")
                await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)
                
                # Selection logic for radio buttons
                radio_selector = f"input[value='{scan_type}']"
                await page.wait_for_selector(radio_selector, timeout=30000)
                await page.click(radio_selector)

                # Fetch available weeks
                options_elements = await page.query_selector_all("#week option")
                week_values = []
                for i in range(min(len(options_elements), weeks)):
                    val = await options_elements[i].get_attribute("value")
                    txt = await options_elements[i].inner_text()
                    week_values.append((val, txt))

                for val, txt in week_values:
                    st.write(f"🔍 Scanning {scan_type}: {txt}")
                    await page.select_option("#week", val)
                    await asyncio.gather(page.wait_for_navigation(), page.click('input[type="submit"][value="Search"]'))
                    
                    results = await page.query_selector_all(".searchresult")
                    for res in results:
                        content = (await res.inner_text()).lower()
                        if any(k in content for k in keywords):
                            link_node = await res.query_selector("a")
                            title = await link_node.inner_text()
                            href = await link_node.get_attribute("href")
                            
                            # Initial info from results page
                            lead_data = {
                                "Week": txt,
                                "Type": scan_type.upper(),
                                "Purpose": title.strip(),
                                "Link": "https://pa.manchester.gov.uk" + href,
                                "Status": "Unknown",
                                "Lead Info": "Checking..."
                            }
                            all_leads.append(lead_data)

            # STEP 3: Deep Scan for Lead Info (Applicant/Agent)
            # We only do this for the matches to save time and avoid bans
            if all_leads:
                st.write("🕵️ Extracting Lead Info and Status...")
                for lead in all_leads:
                    try:
                        await page.goto(lead["Link"], timeout=30000)
                        # Extract Status
                        status_el = await page.query_selector("td:has-text('Status') + td")
                        if status_el:
                            lead["Status"] = await status_el.inner_text()
                        
                        # Navigate to Contacts/Further Info for the 'Lead'
                        await page.click("text='Further Information'", timeout=5000)
                        applicant_el = await page.query_selector("td:has-text('Applicant Name') + td")
                        if applicant_el:
                            lead["Lead Info"] = await applicant_el.inner_text()
                    except:
                        lead["Lead Info"] = "View Link for Details"
                        continue

        except Exception as e:
            st.error(f"Scraper Error: {str(e)[:100]}")
            await page.screenshot(path="debug.png")
            st.image("debug.png")
        finally:
            await browser.close()
    return all_leads

# --- 3. THE ACTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    scan_types = []
    if include_validated: scan_types.append("validated")
    if include_decided: scan_types.append("decided")

    if not scan_types:
        st.warning("Please select at least one scan type (Validated or Decided).")
    elif target_council == "Manchester":
        with st.status(f"Scanning Manchester {scan_types}...", expanded=True):
            leads = asyncio.run(scrape_manchester_comprehensive(weeks_to_scan, scan_types))
        
        if leads:
            df = pd.DataFrame(leads)
            st.success(f"Found {len(df)} High-Value Leads!")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 Export Lead List", df.to_csv(index=False).encode('utf-8'), "urban_leads.csv")
        else:
            st.warning("No matches found. Try broadening keywords or the date range.")

    elif target_council == "Westminster":
        st.error("🚨 Westminster Portal is currently offline due to a cyber incident.")
        st.markdown("""
        **Manual Lead Sourcing for Westminster (2026):**
        1. Click the button below to access their Temporary Planning Register.
        2. Download the latest **XLSX** file.
        3. Filter Column **'Description'** for 'Change of Use' or 'Prior Approval'.
        4. The **'Applicant'** column contains your lead info.
        """)
        st.link_button("Go to Westminster Temporary Register", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Status | Barcelona, Spain")
