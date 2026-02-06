import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime, timedelta
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Planning Lead Pro", page_icon="🏢", layout="wide")

# --- UI HEADER ---
st.title("🏢 Planning Lead Generator")
st.markdown("Automated lead sourcing for Westminster and Manchester councils.")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Settings")
days_back = st.sidebar.slider("Days to look back", 1, 365, 30)
page_limit = st.sidebar.number_input("Pages per council", min_value=1, max_value=50, value=3)
concurrency = st.sidebar.slider("Scan Speed (Concurrency)", 1, 5, 3)

councils_to_run = st.sidebar.multiselect(
    "Select Councils",
    ["Westminster", "Manchester"],
    default=["Westminster", "Manchester"]
)

# --- SCRAPER LOGIC (Your Optimized Version) ---
COUNCILS = {
    "Westminster": "https://idoxpa.westminster.gov.uk",
    "Manchester": "https://pa.manchester.gov.uk",
}

KEYWORDS = ["retail", "shop", "commercial", "office", "mixed use", "restaurant", "class e", "change of use"]

async def scrape_details(context, app_url, council_name, semaphore):
    async with semaphore:
        page = await context.new_page()
        try:
            await page.route("**/*.{png,jpg,jpeg,css,svg}", lambda route: route.abort())
            await page.goto(app_url, wait_until="domcontentloaded", timeout=45000)
            
            async def get_field(labels):
                for label in labels:
                    try:
                        xpath = f"//th[contains(text(), '{label}')]/following-sibling::td"
                        return await page.locator(f"xpath={xpath}").first.inner_text()
                    except: pass
                return ""

            status = await get_field(["Status", "Decision"])
            proposal = await get_field(["Proposal", "Description"])
            address = await get_field(["Address", "Site Address"])
            
            # Switch tabs for contacts
            for tab in ["Contacts", "Further Information"]:
                link = page.get_by_role("link", name=tab, exact=False)
                if await link.count() > 0:
                    await link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    break

            agent = await get_field(["Agent Name", "Agent Company"])
            applicant = await get_field(["Applicant Name", "Organization"])
            target = await get_field(["Agent Address", "Applicant Address", "Address"])

            return {
                "Opportunity": "🔥 APPEAL" if "refuse" in status.lower() else "Live Lead",
                "Status": status,
                "Business": "Hospitality" if "food" in proposal.lower() else "Commercial",
                "Council": council_name,
                "Address": address,
                "Target Contact": target,
                "Agent": agent if agent else "NO AGENT",
                "URL": app_url
            }
        except: return None
        finally: await page.close()

async def run_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh...)")
        semaphore = asyncio.Semaphore(concurrency)
        all_leads = []

        for council in councils_to_run:
            st.write(f"🔎 Scanning {council}...")
            page = await context.new_page()
            try:
                await page.goto(f"{COUNCILS[council]}/online-applications/search.do?action=advanced")
                if await page.locator("input[value='Accept']").count() > 0:
                    await page.click("input[value='Accept']")
                
                date_str = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
                await page.fill("#applicationValidatedStart", date_str)
                await page.click("input[type='submit'][value='Search']")
                
                # Link Harvesting
                links = []
                for _ in range(page_limit):
                    items = await page.query_selector_all(".searchresult")
                    for i in items:
                        if any(k in (await i.inner_text()).lower() for k in KEYWORDS):
                            a = await i.query_selector("a")
                            links.append(COUNCILS[council] + await a.get_attribute("href"))
                    
                    next_p = await page.query_selector("a.next")
                    if next_p: await next_p.click()
                    else: break
                
                tasks = [scrape_details(context, url, council, semaphore) for url in links]
                results = await asyncio.gather(*tasks)
                all_leads.extend([r for r in results if r])
            except Exception as e:
                st.error(f"Error on {council}: {e}")
            finally: await page.close()
            
        await browser.close()
        return all_leads

# --- MAIN APP LOGIC ---
if st.button("🚀 Start Lead Generation"):
    if not councils_to_run:
        st.warning("Please select at least one council.")
    else:
        with st.spinner("Scraping councils... this may take a few minutes."):
            data = asyncio.run(run_scraper())
            
            if data:
                df = pd.DataFrame(data)
                st.success(f"Found {len(df)} leads!")
                
                # Display Interactive Table
                st.dataframe(df, use_container_width=True)
                
                # Download Button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Leads as CSV",
                    data=csv,
                    file_name=f"leads_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv',
                )
            else:
                st.info("No leads found for these settings.")
