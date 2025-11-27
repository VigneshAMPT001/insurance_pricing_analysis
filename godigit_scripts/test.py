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
def extract_cost_breakup_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    def get_val(elem_id, nth=0):
        elements = soup.select(f"#{elem_id}")
        if elements and len(elements) > nth:
            raw = elements[nth].get_text(strip=True)
            return clean_price(raw)       # CLEAN HERE
        return None

    data = {
        "own_damage": get_val("ownDamagePremiumValue"),
        "third_party": get_val("thirdPartyPremiumValue"),
        "addons": get_val("addonPremiumValue"),
        "ncb_discount": get_val("ncbDiscountValue", 0),
        "digit_discount": get_val("ncbDiscountValue", 1),
        "net_premium": get_val("netPremiumValue"),
        "gst": get_val("GSTValue"),
        "final_premium": get_val("finalPremiumValue")
    }

    return data



# -------------------------------
# 2) PLAYWRIGHT VERSION (ASYNC)
# -------------------------------
async def extract_cost_breakup(page):
    # Click to open
    await page.locator(".cost-breakup-card-header").click()
    await page.wait_for_selector(".cost-breakup-card-body", timeout=10000)

    # Extract HTML portion
    html = await page.locator(".cost-breakup-card-body").inner_html()
    return extract_cost_breakup_from_html(html)  # reuse BeautifulSoup parser


# -------------------------------
# 3) TEST WITH LOCAL HTML FILE
# -------------------------------
if __name__ == "__main__":

    html_file_path = Path("/home/ampara/Documents/insurance_pricing_analysis/godigit_scripts/go.html")

    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    print("=== PREMIUM FOOTER (CLEAN NUMBERS) ===")
    result = extract_cost_breakup_from_html(html_content)
    print(json.dumps(result, indent=2))
