import json
from pathlib import Path
from bs4 import BeautifulSoup
# -----------------------------------------------------------
# 1. SCRAPE PLAN INFO (<p id="ComprehensiveWithPiCoverPlanInfo">)
# -----------------------------------------------------------
def scrape_plan_info(html):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("p", id="ComprehensiveWithPiCoverPlanInfo")

    result = []
    for p in items:
        text = p.get_text(strip=True)
        result.append(text)
    return result


# -----------------------------------------------------------
# 2. HANDLE FOOTER PREMIUM BLOCK + CLICK CONTINUE BUTTON
# -----------------------------------------------------------
async def handle_footer_premium_and_continue(page):
    await page.wait_for_selector("#continue-btn", timeout=15000)

    actual_premium = await page.locator("#actualPremiumAmount").inner_text()
    discounted_premium = await page.locator("#premiumAmount").inner_text()
    gst_msg = await page.locator("#gstTextMessage").inner_text()

    print("🔵 Premium Details Extracted:")
    print(f"   👉 Actual Premium: {actual_premium}")
    print(f"   👉 Discounted Premium: {discounted_premium}")
    print(f"   👉 GST Message: {gst_msg}")

    await page.locator("#continue-btn").click()
    print("🟢 Clicked Continue button successfully")

    return {
        "actual_premium": actual_premium,
        "discounted_premium": discounted_premium,
        "gst_text": gst_msg
    }


# -----------------------------------------------------------
# 3. SCRAPE PLAN CARD (Name + Details)
# -----------------------------------------------------------
def scrape_plan_card(html):
    soup = BeautifulSoup(html, "html.parser")

    plan_data = {}

    name_tag = soup.find("div", class_="plan-name")
    plan_data["plan_name"] = name_tag.get_text(strip=True) if name_tag else None

    info_section = soup.find("div", id="ComprehensiveCoverPlanInfo")

    details = []
    if info_section:
        for p in info_section.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                details.append(text)

    plan_data["details"] = details

    return plan_data


# -----------------------------------------------------------
# 4. SCRAPE POLICY DURATION BLOCKS
# -----------------------------------------------------------
def scrape_policy_durations(html):
    soup = BeautifulSoup(html, "html.parser")
    durations = []

    blocks = soup.find_all("div", class_="radio-button-group")

    for block in blocks:
        info = {}

        duration_tag = block.find("div", class_="text-xs")
        info["duration"] = duration_tag.get_text(strip=True) if duration_tag else None

        protected_tag = block.find("div", class_="tp-change-multiYear")
        info["protected_till"] = protected_tag.get_text(strip=True) if protected_tag else None

        best_deal_tag = block.find("span", class_="best-deal")
        info["best_deal"] = best_deal_tag is not None

        durations.append(info)

    return durations


# -----------------------------------------------------------
# 5. SCRAPE IDV BLOCK
# -----------------------------------------------------------
def scrape_idv_block(html):
    soup = BeautifulSoup(html, "html.parser")

    result = {}

    idv_value_tag = soup.select_one(".idv-content-container span.notranslate")
    result["idv_value"] = idv_value_tag.get_text(strip=True) if idv_value_tag else None

    user_range_tag = soup.find("p", class_="motor-idv-titl-text")
    result["popular_range"] = user_range_tag.get_text(strip=True) if user_range_tag else None

    min_tag = soup.find("div", id="minValue")
    max_tag = soup.find("div", id="maxValue")

    result["min_idv"] = min_tag.get_text(strip=True).replace("₹", "").replace(",", "") if min_tag else None
    result["max_idv"] = max_tag.get_text(strip=True).replace("₹", "").replace(",", "") if max_tag else None

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
# 6. SELECT ADD-ON PACKAGE
# -----------------------------------------------------------
async def select_addon_package(page, package_name: str):

    package_ids = {
        "Popular": "#Popularaddon",
        "Popular+": "#Popular\\+addon",
        "Ultimate": "#Ultimateaddon"
    }

    if package_name not in package_ids:
        raise ValueError("Invalid package name. Use: Popular / Popular+ / Ultimate")

    package_selector = package_ids[package_name]

    await page.wait_for_selector(package_selector, timeout=15000)

    await page.locator(package_selector).scroll_into_view_if_needed()

    await page.locator(f"{package_selector} .select-btn").click()

    print(f"🟢 Selected Add-on Package: {package_name}")


# -----------------------------------------------------------
# 7. HANDLE CLAIM, NCB & OWNERSHIP TRANSFER
# -----------------------------------------------------------
async def handle_claim_ncb_and_ownership(page):

    await page.wait_for_selector(".claim-sub-heading", timeout=15000)

    claim_last_year = await page.locator(".claim-sub-heading span.claim-value").nth(0).inner_text()
    ncb_last_year = await page.locator(".claim-sub-heading span.claim-value").nth(1).inner_text()

    print("🔵 Claim & NCB Extracted:")
    print(f"   👉 Claim Last Year: {claim_last_year}")
    print(f"   👉 NCB Last Year:   {ncb_last_year}")

    await page.locator(".material-icons-edit").click()
    print("🟢 Clicked Edit Icon")

    switch_locator = page.locator("#switch-2")
    await switch_locator.scroll_into_view_if_needed()
    await switch_locator.click()

    print("🟢 Ownership transfer toggle clicked")

    return {
        "claim_last_year": claim_last_year,
        "ncb_last_year": ncb_last_year
    }


# -----------------------------------------------------------
# Example usage for local HTML testing
# -----------------------------------------------------------
if __name__ == "__main__":
    html_file_path = Path("godigit_scripts/godigit.html")
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    print("=== PLAN INFO ===")
    print(json.dumps(scrape_plan_info(html_content), indent=2))

    print("=== PLAN CARD ===")
    print(json.dumps(scrape_plan_card(html_content), indent=2))

    print("=== POLICY DURATIONS ===")
    print(json.dumps(scrape_policy_durations(html_content), indent=2))

    print("=== IDV BLOCK ===")
    print(json.dumps(scrape_idv_block(html_content), indent=2))
