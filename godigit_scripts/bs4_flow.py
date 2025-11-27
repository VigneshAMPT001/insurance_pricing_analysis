import json
from pprint import pprint
from bs4 import BeautifulSoup
import asyncio
from playwright.async_api import async_playwright

# -----------------------------------------------------------
# STATIC SCRAPERS (BeautifulSoup)
# -----------------------------------------------------------
def scrape_plan_info(html):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("p", id="ComprehensiveWithPiCoverPlanInfo")
    return [p.get_text(strip=True) for p in items]

def scrape_plan_card(html):
    soup = BeautifulSoup(html, "html.parser")
    plan_data = {}
    name_tag = soup.find("div", class_="plan-name")
    plan_data["plan_name"] = name_tag.get_text(strip=True) if name_tag else None
    info_section = soup.find("div", id="ComprehensiveCoverPlanInfo")
    plan_data["details"] = [p.get_text(strip=True) for p in info_section.find_all("p")] if info_section else []
    return plan_data

def scrape_policy_durations(html):
    soup = BeautifulSoup(html, "html.parser")
    durations = []
    blocks = soup.find_all("div", class_="radio-button-group")
    for block in blocks:
        info = {
            "duration": block.find("div", class_="text-xs").get_text(strip=True) if block.find("div", class_="text-xs") else None,
            "protected_till": block.find("div", class_="tp-change-multiYear").get_text(strip=True) if block.find("div", class_="tp-change-multiYear") else None,
            "best_deal": block.find("span", class_="best-deal") is not None
        }
        durations.append(info)
    return durations

def scrape_idv_block(html):
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    idv_value_tag = soup.select_one(".idv-content-container span.notranslate")
    result["idv_value"] = idv_value_tag.get_text(strip=True) if idv_value_tag else None
    user_range_tag = soup.find("p", class_="motor-idv-titl-text")
    result["popular_range"] = user_range_tag.get_text(strip=True) if user_range_tag else None
    min_tag = soup.find("div", id="minValue")
    max_tag = soup.find("div", id="maxValue")
    result["min_idv"] = min_tag.get_text(strip=True).replace("₹","").replace(",","") if min_tag else None
    result["max_idv"] = max_tag.get_text(strip=True).replace("₹","").replace(",","") if max_tag else None
    slider_handle = soup.select_one(".p-slider-handle")
    if slider_handle:
        result["slider_min"] = slider_handle.get("aria-valuemin")
        result["slider_max"] = slider_handle.get("aria-valuemax")
        result["slider_value"] = slider_handle.get("aria-valuenow")
    else:
        result["slider_min"] = result["slider_max"] = result["slider_value"] = None
    edit_tag = soup.select_one(".edit-idv-container .idv-edit")
    result["edit_available"] = edit_tag is not None
    return result

# -----------------------------------------------------------
# DYNAMIC SCRAPERS (Playwright)
# -----------------------------------------------------------
async def handle_footer_premium_and_continue(page):
    await page.wait_for_selector("#continue-btn", timeout=15000)
    actual_premium = await page.locator("#actualPremiumAmount").inner_text()
    discounted_premium = await page.locator("#premiumAmount").inner_text()
    gst_msg = await page.locator("#gstTextMessage").inner_text()
    await page.locator("#continue-btn").click()
    return {
        "actual_premium": actual_premium,
        "discounted_premium": discounted_premium,
        "gst_text": gst_msg
    }

async def select_addon_package(page, package_name: str):
    package_ids = {"Popular": "#Popularaddon", "Popular+": "#Popular\\+addon", "Ultimate": "#Ultimateaddon"}
    if package_name not in package_ids:
        raise ValueError("Invalid package name. Use: Popular / Popular+ / Ultimate")
    package_selector = package_ids[package_name]
    await page.wait_for_selector(package_selector, timeout=15000)
    await page.locator(package_selector).scroll_into_view_if_needed()
    await page.locator(f"{package_selector} .select-btn").click()
    return package_name

async def handle_claim_ncb_and_ownership(page):
    await page.wait_for_selector(".claim-sub-heading", timeout=15000)
    claim_last_year = await page.locator(".claim-sub-heading span.claim-value").nth(0).inner_text()
    ncb_last_year = await page.locator(".claim-sub-heading span.claim-value").nth(1).inner_text()
    await page.locator(".material-icons-edit").click()
    switch_locator = page.locator("#switch-2")
    await switch_locator.scroll_into_view_if_needed()
    await switch_locator.click()
    return {"claim_last_year": claim_last_year, "ncb_last_year": ncb_last_year}

# -----------------------------------------------------------
# PLAN LOOP
# -----------------------------------------------------------
async def scrape_all_plans(page):
    plans_data = []
    plan_elements = await page.locator("div.prod-con").all()
    count = len(plan_elements)

    for i, plan in enumerate(plan_elements):
        plan_obj = {}
        clickable = plan
        await clickable.scroll_into_view_if_needed()
        print(f"Clicking plan {i+1}/{count}")
        await click_force_js(clickable)  # Your JS click

        # --- DETAILS PAGE ---
        await clear_backdrop(page)
        await page.locator("div.prem-break span", has_text="Premium Breakup").click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)

        await page.wait_for_selector("div.modal-content", timeout=5000)
        premium_html = await page.content()
        plan_details = {
            "plan_premium": parse_premium_breakup(premium_html),
            "idv_range": parse_idv_section(premium_html)
        }
        await page.locator("div.mod-close button.btn-close").click()
        await page.wait_for_timeout(2000)

        await page.locator("div.cover-more", has_text="Know More").click()
        covers_html = await page.content()
        plan_details["benefits_covered"] = parse_cover_sections(covers_html)
        what_covers_close_btn = page.locator("div#knowmorenew button.btn-close")
        await what_covers_close_btn.scroll_into_view_if_needed()
        await what_covers_close_btn.click(force=True)

        plan_title = await plan.locator("div.plan-name").inner_text()
        plan_obj[plan_title] = plan_details
        plans_data.append(plan_obj)

        # GO BACK
        await page.wait_for_selector("div.p-back img", timeout=10000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(5000)
        await do_back_click()
        if i == 1:
            await do_back_click()
        try:
            await page.wait_for_selector("div.box.pro-sel", timeout=10000)
        except:
            await clear_backdrop(page)
            await page.wait_for_timeout(500)
            await do_back_click()
            await page.wait_for_selector("div.box.pro-sel", timeout=10000)

    return plans_data

# -----------------------------------------------------------
# MAIN FUNCTION
# -----------------------------------------------------------
async def main():
    all_data = {}

    # STATIC SCRAPING
    html_file_path = "chola_test.html"
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    all_data["plan_info"] = scrape_plan_info(html_content)
    all_data["plan_card"] = scrape_plan_card(html_content)
    all_data["policy_durations"] = scrape_policy_durations(html_content)
    all_data["idv_block"] = scrape_idv_block(html_content)

    # DYNAMIC SCRAPING
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.godigit.com/motor-insurance/car-flow/car-plan-page")

        # Scrape dynamic plans
        all_data["dynamic_plans"] = await scrape_all_plans(page)
        # Optionally, footer, addon, claim/NCB
        try:
            all_data["footer_premium"] = await handle_footer_premium_and_continue(page)
        except:
            all_data["footer_premium"] = None
        try:
            all_data["selected_addon"] = await select_addon_package(page, "Popular")
        except:
            all_data["selected_addon"] = None
        try:
            all_data["claim_ncb"] = await handle_claim_ncb_and_ownership(page)
        except:
            all_data["claim_ncb"] = None

        await browser.close()

    # SAVE TO JSON
    with open("full_scraped_data.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    pprint(all_data)
    print("✅ All data saved to full_scraped_data.json")

# Run
asyncio.run(main())
