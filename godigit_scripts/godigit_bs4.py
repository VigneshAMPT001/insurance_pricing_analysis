import json
from pathlib import Path
from bs4 import BeautifulSoup
import re


# -------------------------------
# CLEANER: REMOVE ₹, COMMAS, SPACES, SYMBOLS
# -------------------------------
def clean_price(value):
    if not value:
        return None
    value = re.sub(r"[^\d-]", "", value)  # keep only digits and minus sign
    return value


# -------------------------------
# 1) BEAUTIFULSOUP VERSION (HTML FILE TESTING)
# -------------------------------
def scrape_cost_breakup(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    def get_val(elem_id, nth=0):
        elements = soup.select(f"#{elem_id}")
        if elements and len(elements) > nth:
            raw = elements[nth].get_text(strip=True)
            return clean_price(raw)  # CLEAN HERE
        return None

    data = {
        "own_damage": get_val("ownDamagePremiumValue"),
        "third_party": get_val("thirdPartyPremiumValue"),
        "addons": get_val("addonPremiumValue"),
        "ncb_discount": get_val("ncbDiscountValue", 0),
        "digit_discount": get_val("ncbDiscountValue", 1),
        "net_premium": get_val("netPremiumValue"),
        "gst": get_val("GSTValue"),
        "final_premium": get_val("finalPremiumValue"),
    }

    return data


def parse_addon_pack(html):
    soup = BeautifulSoup(html, "html.parser")

    data = {}

    # Pack Name (e.g., Ultimate pack)
    name_tag = soup.select_one("p.plan-name")
    data["pack_name"] = name_tag.get_text(strip=True) if name_tag else None

    # Extract count — e.g., (8 add-on)
    if data["pack_name"]:
        # Example: "Ultimate pack (8 add-on)"
        import re

        match = re.search(r"\((.*?)\)", data["pack_name"])
        data["addon_count"] = match.group(1) if match else None

    # Monthly premium — inside label.addon-premium
    premium_label = soup.select_one("label.addon-premium")
    data["premium"] = premium_label.get_text(strip=True) if premium_label else None

    # Individual add-ons — these are inside <label class="text-xs ...">
    addon_items = soup.select("div.subcover-list label")
    addons = []

    for item in addon_items:
        txt = item.get_text(strip=True)
        # remove leading "done" icon text if present
        txt = txt.replace("done", "").strip()
        addons.append(txt)

    data["addons"] = addons

    return data


def parse_popular(html):
    soup = BeautifulSoup(html, "html.parser")

    result = {}

    # --- PACK NAME ---
    name_tag = soup.select_one("p.plan-name")
    if name_tag:
        name = name_tag.get_text(strip=True)
        result["pack_name"] = name

        # Extract count e.g., (2 add-on)
        m = re.search(r"\((.*?)\)", name)
        result["addon_count"] = m.group(1) if m else None
    else:
        result["pack_name"] = None
        result["addon_count"] = None

    # --- ADDON LIST ---
    addons = []
    addon_tags = soup.select("div.subcover-list label")
    for lab in addon_tags:
        txt = lab.get_text(strip=True)

        # Remove the word "done" from icon
        txt = txt.replace("done", "").strip()

        addons.append(txt)

    result["addons"] = addons

    return result


def extract_policy_durations(html):
    """
    Extracts all policy durations (like '1 year', '3 year') from the given HTML.
    Returns a list of strings.
    """
    soup = BeautifulSoup(html, "html.parser")
    durations = []

    # Select all divs that contain the duration text
    duration_divs = soup.select("div.radio-button-group div.text-xs.font-bold")

    for div in duration_divs:
        text = div.get_text(strip=True)
        if text:  # only add non-empty strings
            durations.append(text)

    return durations


def extract_ncb_percentage_and_value(html):
    """
    Extracts NCB percentage and premium value from the HTML.
    Returns a tuple: (percentage, value) as integers.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract NCB percentage (e.g., 45%)
    perc_elem = soup.select_one("div.ncb-protect-cover-section p.font-extrabold")
    percentage = None
    if perc_elem:
        perc_text = perc_elem.get_text()
        perc_match = re.search(r"(\d+)", perc_text)
        if perc_match:
            percentage = int(perc_match.group())

    # Extract NCB premium value (e.g., ₹557)
    value_elem = soup.select_one("div.ncb-protect-cover-section p.font-bold")
    value = None
    if value_elem:
        value_text = value_elem.get_text()
        value_match = re.search(r"(\d+)", value_text.replace(",", ""))
        if value_match:
            value = int(value_match.group())

    return percentage, value


def parse_popular_pack(html):
    soup = BeautifulSoup(html, "html.parser")

    result = {}

    # --- PACK NAME ---
    name_tag = soup.select_one("p.plan-name")
    if name_tag:
        name = name_tag.get_text(strip=True)
        result["pack_name"] = name

        # extract count e.g. (5 add-on)
        m = re.search(r"\((.*?)\)", name)
        result["addon_count"] = m.group(1) if m else None
    else:
        result["pack_name"] = None
        result["addon_count"] = None

    # --- ADDONS ---
    addons_tags = soup.select("div.subcover-list label")
    addons = []
    for tag in addons_tags:
        txt = tag.get_text(strip=True)
        txt = txt.replace("done", "").strip()
        addons.append(txt)

    result["addons"] = addons

    # --- NO PREMIUM HERE ---
    result["premium"] = None  # popular pack has no premium value

    return result


def extract_extra_addons(html):
    soup = BeautifulSoup(html, "html.parser")
    addons = []

    addon_blocks = soup.select("div.extra-package-addon")

    for block in addon_blocks:
        # --- Checkbox ID & value ---
        checkbox = block.select_one("input[type='checkbox']")
        addon_id = checkbox.get("id") if checkbox else None
        addon_value = checkbox.get("value") if checkbox else None

        # --- Add-on name ---
        name_elem = block.select_one("span.checkbox-label")
        name = name_elem.get_text(strip=True) if name_elem else None

        # --- Price ---
        price_elem = block.select_one("div.price")
        price = None
        price_term = None

        if price_elem:
            price_text = price_elem.get_text(" ", strip=True)
            price_match = re.search(r"(\d+)", price_text.replace(",", ""))
            if price_match:
                price = int(price_match.group())

            # term = month / year
            term_elem = block.select_one("span.per-term")
            if term_elem:
                price_term = term_elem.get_text(strip=True)

        # --- Sub-cover text (optional line under name) ---
        subcover_elem = block.select_one("span.checkbox-subcover")
        subcover = subcover_elem.get_text(strip=True) if subcover_elem else None

        addons.append(
            {
                "id": addon_id,
                "value": addon_value,
                "name": name,
                "subcover": subcover,
                "price": price,
                "price_term": price_term,
            }
        )

    return addons


def extract_addon_names(html):
    """
    Extracts all add-on names from the given HTML of a package/add-on section.
    Returns a list of strings.
    """
    soup = BeautifulSoup(html, "html.parser")
    addon_names = []

    # Select all label elements inside the subcover-list div
    labels = soup.select("div.subcover-list label")

    for label in labels:
        # Get text, remove extra whitespace, and ignore empty strings
        text = label.get_text(strip=True)
        # Remove leading "done" if present (from material-icons)
        text = text.replace("done", "").strip()
        if text:
            addon_names.append(text)

    return addon_names


def clean_number(text):
    """Extract only digits and decimal values."""
    if not text:
        return None
    text = re.sub(r"[^0-9.]", "", text)
    return text.strip() if text else None


def parse_trust_card_numbers_only(html):
    soup = BeautifulSoup(html, "html.parser")

    result = {"highlights": [], "disclaimer": None}

    items = soup.select("div.carousel-item")

    for item in items:
        spans = item.select("div.text-block span")
        if len(spans) >= 2:
            title_raw = spans[0].get_text(" ", strip=True)
            subtitle_raw = spans[1].get_text(" ", strip=True)

            # Extract ONLY numeric value from title
            number_value = clean_number(title_raw)

            result["highlights"].append(
                {
                    "value": number_value,  # ONLY number
                    "subtitle": subtitle_raw,  # full sentence untouched
                }
            )

    # Extract disclaimer without modifying it
    disclaimer_tag = soup.find("span", string=lambda x: x and "Disclaimer" in x)
    if disclaimer_tag:
        result["disclaimer"] = disclaimer_tag.get_text(strip=True)

    return result


# 1. SCRAPE PLAN INFO
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
# 2. HANDLE FOOTER PREMIUM BLOCK + CONTINUE
# -----------------------------------------------------------
async def handle_footer_premium_and_continue(page):
    await page.wait_for_selector("#continue-btn", timeout=15000)

    # CLEANED HERE
    actual_premium = clean_price(
        await page.locator("#actualPremiumAmount").inner_text()
    )
    discounted_premium = clean_price(await page.locator("#premiumAmount").inner_text())
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
        "gst_text": gst_msg,
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
        info["protected_till"] = (
            protected_tag.get_text(strip=True) if protected_tag else None
        )

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
    result["idv_value"] = (
        clean_price(idv_value_tag.get_text(strip=True)) if idv_value_tag else None
    )

    user_range_tag = soup.find("p", class_="motor-idv-titl-text")
    result["popular_range"] = (
        user_range_tag.get_text(strip=True) if user_range_tag else None
    )

    # CLEANED VALUES
    min_tag = soup.find("div", id="minValue")
    max_tag = soup.find("div", id="maxValue")

    result["min_idv"] = clean_price(min_tag.get_text(strip=True)) if min_tag else None
    result["max_idv"] = clean_price(max_tag.get_text(strip=True)) if max_tag else None

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
        "Ultimate": "#Ultimateaddon",
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

    claim_last_year = (
        await page.locator(".claim-sub-heading span.claim-value").nth(0).inner_text()
    )
    ncb_last_year = (
        await page.locator(".claim-sub-heading span.claim-value").nth(1).inner_text()
    )

    print("🔵 Claim & NCB Extracted:")
    print(f"   👉 Claim Last Year: {claim_last_year}")
    print(f"   👉 NCB Last Year:   {ncb_last_year}")

    await page.locator(".material-icons-edit").click()
    print("🟢 Clicked Edit Icon")

    switch_locator = page.locator("#switch-2")
    await switch_locator.scroll_into_view_if_needed()
    await switch_locator.click()

    print("🟢 Ownership transfer toggle clicked")

    return {"claim_last_year": claim_last_year, "ncb_last_year": ncb_last_year}


# -----------------------------------------------------------
# 8. PARSE FOOTER PREMIUM BLOCK (BS4) CLEANED
# -----------------------------------------------------------
def parse_comprehensive_plan_footer(html):
    soup = BeautifulSoup(html, "html.parser")

    data = {}

    actual = soup.find("p", id="actualPremiumAmount")
    data["actual_premium"] = (
        clean_price(actual.get_text(strip=True)) if actual else None
    )

    discounted = soup.find("p", id="premiumAmount")
    data["discounted_premium"] = (
        clean_price(discounted.get_text(strip=True)) if discounted else None
    )

    gst = soup.find("p", id="gstTextMessage")
    data["gst_text"] = gst.get_text(strip=True) if gst else None

    return data


def extract_idv_values(html):
    soup = BeautifulSoup(html, "html.parser")

    def clean_number(text):
        if not text:
            return None
        return int(re.sub(r"[^\d]", "", text))

    # --- Main IDV shown at top ---
    main_idv_elem = soup.select_one("p span.notranslate")
    main_idv = (
        clean_number(main_idv_elem.get_text(strip=True)) if main_idv_elem else None
    )

    # --- Input box min/max attributes ---
    input_field = soup.select_one("input#idvAmountField")
    input_min = clean_number(input_field.get("min")) if input_field else None
    input_max = clean_number(input_field.get("max")) if input_field else None

    # --- Bottom min/max displayed text (₹ 3,13,000 etc.) ---
    min_text_elem = soup.select_one("#minValue p")
    max_text_elem = soup.select_one("#maxValue p")

    slider_min = (
        clean_number(min_text_elem.get_text(strip=True)) if min_text_elem else None
    )
    slider_max = (
        clean_number(max_text_elem.get_text(strip=True)) if max_text_elem else None
    )

    return {
        "main_idv": main_idv,
        "input_min": input_min,
        "input_max": input_max,
        "slider_min": slider_min,
        "slider_max": slider_max,
    }


# -------------------------------
# 2) PLAYWRIGHT VERSION (ASYNC)
# -------------------------------
async def extract_cost_breakup(page):
    # Click to open
    await page.locator(".cost-breakup-card-header").click()
    await page.wait_for_selector(".cost-breakup-card-body", timeout=10000)

    # Extract HTML portion
    html = await page.locator(".cost-breakup-card-body").inner_html()
    return scrape_cost_breakup(html)  # reuse BeautifulSoup parser


# -------------------------------
# 3) TEST WITH LOCAL HTML FILE
# -------------------------------
if __name__ == "__main__":

    html_file_path = Path(
        "/home/ampara/Documents/insurance_pricing_analysis/godigit_scripts/go.html"
    )

    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    print("=== PREMIUM FOOTER (CLEAN NUMBERS) ===")
    result = scrape_cost_breakup(html_content)
    print(json.dumps(result, indent=2))

    print("=== add on pack ===")
    result = parse_addon_pack(html_content)
    print(json.dumps(result, indent=2))

    print("=== Popular ===")
    result = parse_popular_pack(html_content)
    print(json.dumps(result, indent=2))

    print("=== Park2 ===")
    result = parse_popular(html_content)
    print(json.dumps(result, indent=2))

    print("=== Trust card  ===")
    result = parse_trust_card_numbers_only(html_content)
    print(json.dumps(result, indent=2))

    print("=== policy duration  ===")
    result = extract_policy_durations(html_content)
    print(json.dumps(result, indent=2))

    print("=== extra add on  ===")
    result = extract_addon_names(html_content)
    print(json.dumps(result, indent=2))

    print("=== extra NCB value ===")
    result = extract_ncb_percentage_and_value(html_content)
    print(json.dumps(result, indent=2))

    print("=== extra add on ===")
    result = extract_extra_addons(html_content)
    print(json.dumps(result, indent=2))

    print("=== PLAN INFO ===")
    print(json.dumps(scrape_plan_info(html_content), indent=2))

    print("=== PLAN CARD ===")
    print(json.dumps(scrape_plan_card(html_content), indent=2))

    print("=== POLICY DURATIONS ===")
    print(json.dumps(scrape_policy_durations(html_content), indent=2))

    print("=== IDV BLOCK ===")
    print(json.dumps(scrape_idv_block(html_content), indent=2))

    print("=== PREMIUM FOOTER ===")
    print(json.dumps(parse_comprehensive_plan_footer(html_content), indent=2))

    print("=== extra idv ===")
    print(json.dumps(extract_idv_values(html_content), indent=2))
