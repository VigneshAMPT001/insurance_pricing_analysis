# scrape_digit_planpage.py
import json
import time
from playwright.sync_api import sync_playwright

URL = "https://www.godigit.com/motor-insurance/car-flow/car-plan-page?session=GgGXoShFWnllmdHYwbOTMK"

def safe_get_text(page, selector):
    try:
        el = page.locator(selector)
        if el.count() > 0:
            return el.first.text_content().strip()
    except:
        pass
    return None

def safe_get_all(page, selector):
    try:
        els = page.locator(selector)
        out = []
        for i in range(els.count()):
            out.append(els.nth(i).text_content().strip())
        return out
    except:
        return []

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()

        print("Loading page…")
        page.goto(URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(5)

        data = {}

        # ================================================================
        # 1) CLAIM SECTION (inside the big container chain you described)
        # ================================================================
        data["claim_heading"] = safe_get_text(
            page,
            ".claim-section .claim-sub-heading"
        )
        data["claim_value"] = safe_get_text(
            page,
            ".claim-section .claim-value"
        )

        # ================================================================
        # 2) TOTAL PREMIUM BOX (footer-card-container)
        # ================================================================
        data["actual_premium"] = safe_get_text("#actualPremiumAmount")
        data["plan_amount"] = safe_get_text(".choose-plan-amount")
        data["premium_amount"] = safe_get_text("#premiumAmount")
        data["discounted_amount"] = safe_get_text(".choose-plan-discounted-amount")
        data["gst_text"] = safe_get_text("#gstTextMessage")

        # ================================================================
        # 3) ADDON SECTION
        # ================================================================
        data["addon_labels"] = safe_get_all(
            page,
            ".addon-name-info .checkbox-label"
        )

        data["pa_owner_addon"] = safe_get_all(
            page,
            ".addon-name-info .paOwner-addon"
        )

        data["per_term_addon"] = safe_get_all(
            page,
            ".addon-name-info .per-term"
        )

        # ================================================================
        # 4) MOTOR IDV SECTION
        # ================================================================
        data["motor_idv_text"] = safe_get_text(
            ".motor-idv-content .idv-content-container .notranslate"
        )

        # ================================================================
        # Save JSON
        # ================================================================
        with open("digit_carplan_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print("\n✔ SCRAPED DATA SAVED TO: digit_carplan_data.json")
        browser.close()

if __name__ == "__main__":
    main()
