import streamlit as st
import os
import sys
import subprocess
import asyncio
import pandas as pd
from datetime import datetime, timedelta
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
    weeks_to_scan = st.slider("Weeks to look back", 1, 8, 4)
    st.divider()
    st.info("Tailored for Urban Planning Startups.")

# --- 2. THE ADVANCED SCRAPER ---
async def scrape_manchester_stealth(weeks):
    all_leads = []
    keywords = ["prior approval", "change of use", "conversion", "commercial", "class ma", "office", "retail", "shop", "restaurant"]
    base_url = "https://pa.manchester.gov.uk/online-applications"
    
    async with async_playwright() as p:
        # Launching with stealth-like arguments
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        try:
            # STEP 1: Prime the session (The "Front Door")
            st.write("🔑 Priming Security Session...")
            await page.goto(f"{base_url}/main.do?action=terms", timeout=60000)
            
            # STEP 2: Handle Disclaimer
            # We wait for the 'Accept' button to exist
            accept_selector = 'input[type="submit"][value*="Accept"], input[name="agree"]'
            if await page.query_selector(accept_selector):
                st.write("🔓 Unlocking Portal...")
                await page.click(accept_selector)
                await page.wait_for_load_state("networkidle")
            
            # STEP 3: Navigate to Weekly List with the now-active session cookie
            st.write("📅 Accessing Weekly Register...")
            await page.goto(f"{base_url}/search.do?action=weeklyList", timeout=60000)
            
            # Check if we were redirected back to terms (Safety check)
            if "terms" in page.url:
                st.write("⚠️ Re-attempting handshake...")
                await page.click(accept_selector)
                await page.wait_for_load_state("networkidle")

            # STEP 4: Interact with the Search Form
            # We wait for the dropdown to be visible
            await page.wait_for_selector("#weeklyListDisplayType", timeout=30000)
            await page.select_option("#weeklyListDisplayType", "validated")
            
            # Get the list of weeks
            options = await page.query_selector_all("#week option")
            for i in range(min(len(options), weeks)):
                current_options = await page.query_selector_all("#week option")
                val = await current_options[i].get_attribute("value")
                text = await current_options[i].inner_text()
                
                st.write(f"🔍 Scanning Week: **{text}**")
                await page.select_option("#week", val)
                
                # Click Search and wait for result list
                async with page.expect_navigation():
                    await page.click('input[type="submit"]')
                
                # Scrape results if any exist
                results = await page.query_selector_all(".searchresult")
                for res in results:
                    content = (await res.inner_text()).lower()
                    if any(k in content for k in keywords):
                        link_node = await res.query_selector("a")
                        title = await link_node.inner_text()
                        href = await link_node.get_attribute("href")
                        all_leads.append({
                            "Week": text,
                            "Project": title.strip(),
                            "Type": "PRIORITY" if "prior approval" in content else "Standard",
                            "Link": "https://pa.manchester.gov.uk" + href
                        })
                
                # Navigate back to Weekly List for next iteration
                await page.goto(f"{base_url}/search.do?action=weeklyList")
                await page.wait_for_selector("#week")

        except Exception as e:
            # SCREENSHOT FOR DEBUGGING
            # This is the "Solution" part - if it fails, it shows us what happened.
            st.error(f"Scraper Error: {str(e)[:150]}")
            screenshot_path = "debug_screenshot.png"
            await page.screenshot(path=screenshot_path)
            st.image(screenshot_path, caption="What the Scraper sees right now")
        finally:
            await browser.close()
    return all_leads

# --- 3. THE ACTION ---
if st.button(f"🚀 Scout {target_council} Now"):
    if target_council == "Manchester":
        with st.status("Searching Manchester...", expanded=True) as status:
            leads = asyncio.run(scrape_manchester_stealth(weeks_to_scan))
            status.update(label="Scout Complete!", state="complete")
        
        if leads:
            df = pd.DataFrame(leads)
            st.success(f"Found {len(df)} High-Value Leads!")
            st.dataframe(df, column_config={"Link": st.column_config.LinkColumn("View Case")}, use_container_width=True)
            st.download_button("📥 Download CSV", df.to_csv(index=False).encode('utf-8'), "leads.csv")
        else:
            st.warning("No commercial leads found. Try a different council or wider search.")

    elif target_council == "Westminster":
        st.error("🚨 Westminster Portal is currently offline due to a cyber-attack.")
        st.link_button("Go to Westminster Temporary Manual List", "https://www.westminster.gov.uk/planning-building-control-and-environmental-regulations/planning-applications/search-and-comment-planning-applications-and-register-email-notifications")

st.divider()
st.caption("Urban Planning Startup Tool | 2026 Live Status | Barcelona, Spain.")
