import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from playwright.async_api import async_playwright

# --- 1. ENGINE INITIALIZATION ---
if "browser_ready" not in st.session_state:
    with st.spinner("🏗️ Calibrating Lead Engine..."):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            st.session_state.browser_ready = True
        except Exception as e:
            st.error(f"Setup Error: {e}")

st.set_page_config(page_title="Urban Planning Lead Scout", page_icon="🏢", layout="wide")
st.title("🏢 Urban Planning Lead Scout")

with st.sidebar:
    st.header("Search Parameters")
    target_council = st.selectbox("Select Council", ["Manchester", "Westminster"])
    weeks_to_scan = st.slider("Weeks to scan (Max 15)", 1, 15, 4)
    st.divider()
    st.info("Direct scan of Manchester Idox Portal.")

# --- 2. THE FORCE-NAVIGATE SCRAPER ---
async def scrape_manchester_final_fix(weeks):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail", "shop", "restaurant"]
    base_url = "https://pa.manchester.gov.uk/online-applications"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0")
        page = await context.new_page()
        
        try:
            # STEP 1: FORCE THE TERMS ACCEPTANCE
            st.write("🔓 Forcing Security Handshake...")
            await page.goto(f"{base_url}/main.do?action=terms", timeout=60000)
            accept_btn = await page.query_selector('input[type="submit"][value*="Accept"]')
            if accept_btn:
                await accept_btn.click()
                await page.wait_for_load_state("networkidle")

            # STEP 2: SEQUENTIAL SCAN (VALIDATED THEN DECIDED)
            for mode in ["validated", "decided"]:
                st.write(f"📂 **Searching: {mode.upper()}**")
                
                # Navigate to the search page directly
                await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)
                
                # If we are stuck on terms, click again
                if "terms" in page.url:
                    await page.click('input[type="submit"][value*="Accept"]')
                    await page.goto(f"{base_url}/search.do?action=weeklyList")

                # WAITING FOR ELEMENTS - Using a more flexible 'visible' check
                radio_sel = f"input[value='{mode}']"
                await page.wait_for_selector(radio_sel, state="visible", timeout=30000)
                await page.click(radio_sel)

                # STEP 3: DYNAMIC WEEK SELECTION (Up to 15 weeks back)
                await page.wait_for_selector("#week", timeout=10000)
                options = await page.query_selector_all("#week option")
                
                # We extract the specific values for the number of weeks requested
                available_weeks = []
                for i in range(min(len(options), weeks)):
                    val = await options[i].get_attribute("value")
                    label = await options[i].inner_text()
                    available_weeks.append((val, label))

                for val, label in available_weeks:
                    st.write(f"🔍 Checking Week: {label}")
                    await page.select_option("#week", val)
                    
                    # Submit Search
                    async with page.expect_navigation(timeout=60000):
                        await page.click('input[type="submit"][value="Search"]')
                    
                    # STEP 4: RESULT SCRAPING
                    results = await page.query_selector_all(".searchresult")
                    for res in results:
                        text = (await res.inner_text()).lower()
                        if any(k in text for k in keywords):
                            link_node = await res.query_selector("a")
                            title = await link_node.inner_text()
                            href = await link_node.get_attribute("href")
                            
                            all_leads.append({
                                "Mode": mode.upper(),
                                "Week": label,
                                "Purpose": title.strip(),
                                "Link": "https://pa.manchester.gov.uk" + href,
                                "Status": "Pending Deep Scan",
                                "Lead Name": "Pending Deep Scan"
                            })
                    
                    # Jump back to search form for the next week
                    await page.goto(f"{base_url}/search.do?action=weeklyList")
                    await page.click(radio_sel)

            # STEP 5: DEEP SCAN (CONTACT EXTRACTION)
            if all_leads:
                st.write("🕵️ Extracting Lead Names and Project Status...")
                for lead in all_leads:
                    try:
                        await page.goto(lead["Link"], timeout=30000)
                        # Extract Status
                        status_el = await page.query_selector("td:has-text('Status') + td")
                        if status_el: lead["Status"] = await status_el.inner_text()
                        
                        # Extract Lead Name (from Further Information tab)
                        await page.click("text='Further Information'", timeout=5000)
                        name_el = await page.query_selector("td:has-text('Applicant Name') + td")
                        if name_el: lead["Lead Name"] = await name_el.inner_text()
                    except:
                        lead["Lead Name"] = "Click Link for Info"

        except Exception as e:
            st.error(f"⚠️ Technical Glitch: {e}")
            await page.screenshot(path="fail.png")
            st.image("fail.png", caption="Last view before error")
        finally:
            await browser.close()
    return all_leads

# --- 3. ACTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    if target_council == "Manchester":
        with st.status("Executing Multi-Week Lead Hunt...", expanded=True):
            leads = asyncio.run(scrape_manchester_final_fix(weeks_to_scan))
        
        if leads:
            df = pd.DataFrame(leads)
            st.success(f"Success! Found {len(df)} High-Quality Leads.")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 Save CSV", df.to_csv(index=False).encode('utf-8'), "leads.csv")
        else:
            st.warning("No commercial leads found. Try searching back further (Max 15 weeks).")

    elif target_council == "Westminster":
        st.error("🚨 Westminster Portal is currently offline.")
        st.link_button("Access Westminster Manual List", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Scout")
