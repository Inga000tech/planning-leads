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
    weeks_to_scan = st.slider("Weeks to look back", 1, 8, 2)
    st.divider()
    st.info("Targets: Prior Approvals & Change of Use.")

# --- 2. THE SEQUENTIAL SCRAPER ---
async def scrape_manchester_dual(weeks):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail", "shop", "restaurant"]
    base_url = "https://pa.manchester.gov.uk/online-applications"
    search_modes = ["validated", "decided"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        try:
            # --- MANDATORY HANDSHAKE ---
            st.write("🔑 Clearing Security Wall...")
            await page.goto(f"{base_url}/main.do?action=terms", timeout=60000)
            accept = await page.query_selector('input[type="submit"][value*="Accept"]')
            if accept: 
                await accept.click()
                await page.wait_for_load_state("networkidle")

            for mode in search_modes:
                st.write(f"📂 **Mode: {mode.upper()}**")
                
                # Navigate to Weekly List
                await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)
                
                # RE-CHECK TERMS: If we get redirected back to terms, click accept again
                if "terms" in page.url:
                    accept = await page.query_selector('input[type="submit"][value*="Accept"]')
                    if accept: await accept.click()
                    await page.goto(f"{base_url}/search.do?action=weeklyList")

                # SELECT THE RADIO BUTTON
                # We use a broader selector to ensure it doesn't fail on partial matches
                radio_selector = f"input[type='radio'][value='{mode}']"
                await page.wait_for_selector(radio_selector, timeout=30000)
                await page.click(radio_selector)
                
                # Fetch available weeks
                await page.wait_for_selector("#week", timeout=10000)
                options = await page.query_selector_all("#week option")
                week_list = []
                for i in range(min(len(options), weeks)):
                    val = await options[i].get_attribute("value")
                    txt = await options[i].inner_text()
                    week_list.append((val, txt))

                for val, txt in week_list:
                    st.write(f"🔍 Scanning {mode} - {txt}")
                    await page.select_option("#week", val)
                    
                    # Search click
                    await asyncio.gather(
                        page.wait_for_load_state("networkidle"),
                        page.click('input[type="submit"][value="Search"]')
                    )
                    
                    # Scrape preliminary results
                    results = await page.query_selector_all(".searchresult")
                    for res in results:
                        content = (await res.inner_text()).lower()
                        if any(k in content for k in keywords):
                            link_node = await res.query_selector("a")
                            title = await link_node.inner_text()
                            href = await link_node.get_attribute("href")
                            
                            all_leads.append({
                                "Mode": mode.upper(),
                                "Week": txt,
                                "Purpose": title.strip(),
                                "Link": "https://pa.manchester.gov.uk" + href,
                                "Status": "Processing...",
                                "Lead Info": "Processing..."
                            })
                    
                    # Go back for next week and re-select mode
                    await page.goto(f"{base_url}/search.do?action=weeklyList")
                    await page.wait_for_selector(radio_selector)
                    await page.click(radio_selector)

            # --- DEEP SCAN FOR CONTACTS ---
            if all_leads:
                st.write("🕵️ Extracting Lead Names & Status...")
                for lead in all_leads:
                    try:
                        await page.goto(lead["Link"], timeout=30000)
                        # Grab Status
                        status_el = await page.query_selector("td:has-text('Status') + td")
                        if status_el: lead["Status"] = await status_el.inner_text()
                        
                        # Grab Applicant Name (Lead Info)
                        await page.click("text='Further Information'", timeout=5000)
                        applicant = await page.query_selector("td:has-text('Applicant Name') + td")
                        if applicant: lead["Lead Info"] = await applicant.inner_text()
                    except:
                        lead["Lead Info"] = "View Case Link"

        except Exception as e:
            st.error(f"Technical Glitch: {str(e)[:100]}")
            await page.screenshot(path="error_state.png")
            st.image("error_state.png", caption="Current view of the site")
        finally:
            await browser.close()
    return all_leads

# --- 3. EXECUTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    if target_council == "Manchester":
        with st.status("Running Sequential Dual-Pass Scan...", expanded=True):
            data = asyncio.run(scrape_manchester_dual(weeks_to_scan))
        
        if data:
            df = pd.DataFrame(data)
            st.success(f"Found {len(df)} High-Value Leads!")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8'), "leads.csv")
        else:
            st.warning("No commercial matches found. Try increasing the 'Look back' slider.")

    elif target_council == "Westminster":
        st.error("🚨 Westminster Portal Offline (Cyber Incident)")
        st.markdown("Westminster is currently publishing **manual XLSX files**. Use the button below to find the latest 'Temporary Planning Register'.")
        st.link_button("Access Westminster Manual List", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | Barcelona, Spain")
