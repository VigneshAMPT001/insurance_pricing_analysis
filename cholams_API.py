import asyncio, json, os
from playwright.async_api import async_playwright

CAR_NUMBER = "MH12VZ2302"
PHONE = "8325369134"

INSURANCE_NAME = "cholams"
HOME_URL = "https://www.cholainsurance.com/"
PREMIUM_API_URL = "https://digital.cholainsurance.com/api/v1/masterdata/quote"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_OUTPUT_DIR = os.path.join(BASE_DIR, "insurer", INSURANCE_NAME, CAR_NUMBER)
os.makedirs(ROOT_OUTPUT_DIR, exist_ok=True)


# ----------------------------------------------------
# HELPERS
# ----------------------------------------------------
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def save_html(path, html):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

async def capture_premium_api(context):
    try:
        resp = await context.wait_for_event(
            "response",
            timeout=30000,
            predicate=lambda r: PREMIUM_API_URL in r.url
        )
        return await resp.json()
    except:
        return None

async def extract_plan_details(page):
    """Extract plan name, premium, IDV, coverage text, features etc."""
    details = {}

    # TITLE
    try:
        title = await page.locator("div.prod-dtl-tit, .plan-title, h1").first.inner_text()
        details["title"] = title.strip()
    except:
        details["title"] = ""

    # PREMIUM
    try:
        prem = await page.locator("span#premiumAmount, .premium-amount").first.inner_text()
        details["premium"] = prem.strip()
    except:
        details["premium"] = ""

    # IDV
    try:
        idv = await page.locator("span#idvValue, .idv-value").first.inner_text()
        details["IDV"] = idv.strip()
    except:
        details["IDV"] = ""

    # COVERAGE LIST
    try:
        coverages = await page.locator("ul li").all_inner_texts()
        details["coverages"] = coverages
    except:
        details["coverages"] = []

    return details


# ----------------------------------------------------
# MAIN WORKFLOW
# ----------------------------------------------------
async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.grant_permissions(["geolocation"])   # Added as requested
        page = await context.new_page()

        # ----------------------------------------
        # QUOTE PAGE
        # ----------------------------------------
        await page.goto(HOME_URL, wait_until="domcontentloaded")
        await page.wait_for_selector("div.product-container")

        await page.fill("input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-mob-no", PHONE)
        await page.fill("input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-reg-no", CAR_NUMBER)

        async with page.expect_navigation():
            await page.click("#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_quote-btn")

        await page.wait_for_selector("div.d-grid")
        await page.click("div.d-grid button")

        await page.wait_for_selector("div.custom-callender input#demo-14")
        await page.click("div.custom-callender input#demo-14")

        YES_LABEL = "div.mod-body:has(input#card1) label[for='card1']"
        await page.wait_for_selector(YES_LABEL)
        await page.click(YES_LABEL)

        # ----------------------------------------
        # WAIT FOR ALL PLANS TO LOAD
        # ----------------------------------------
        await page.wait_for_selector("div.prod-con", timeout=120000)

        # Extract all plan cards
        plan_cards = await page.locator("div.prod-con .tit").all()
        plans_list = []
        for i, card in enumerate(plan_cards):
            title = (await card.inner_text()).strip()
            plans_list.append((i, title))

        master_json = {}

        # ----------------------------------------
        # PROCESS EACH PLAN SEPARATELY
        # ----------------------------------------
        for index, title in plans_list:
            safe_title = title.replace(" ", "_").replace("/", "_")

            PLAN_DIR = os.path.join(ROOT_OUTPUT_DIR, safe_title)
            os.makedirs(PLAN_DIR, exist_ok=True)

            print(f"\n==============================")
            print(f"Processing PLAN → {safe_title}")
            print(f"==============================")

            # Click the nth plan
            nth_selector = f"div.prod-con .tit >> nth={index}"
            async with page.expect_navigation(wait_until="domcontentloaded"):
                await page.locator(nth_selector).click()

            # 1. CAPTURE API JSON
            api_json = await capture_premium_api(context)
            if api_json:
                save_json(os.path.join(PLAN_DIR, "API.json"), api_json)
                master_json[safe_title] = api_json
                print("✔ API saved")
            else:
                print("✖ No API captured")

            # 2. SAVE HTML
            html = await page.content()
            save_html(os.path.join(PLAN_DIR, "PAGE.html"), html)
            print("✔ HTML saved")

            # 3. EXTRACT PLAN DETAILS FROM HTML
            details = await extract_plan_details(page)
            save_json(os.path.join(PLAN_DIR, "DETAILS.json"), details)
            print("✔ DETAILS extracted")

            # Return back to list
            await page.go_back(wait_until="domcontentloaded")
            await page.wait_for_selector("div.prod-con")

        # ----------------------------------------
        # MASTER SUMMARY
        # ----------------------------------------
        save_json(os.path.join(ROOT_OUTPUT_DIR, "ALL_PLANS.json"), master_json)
        print("\n✔ ALL_PLANS.json saved")

        await browser.close()

asyncio.run(run())
