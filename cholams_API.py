import asyncio, json, os
from playwright.async_api import async_playwright

CAR_NUMBER = "MH12VZ2302"
PHONE = "8325369134"
HOME_URL = "https://www.cholainsurance.com/"

# Keywords that identify premium or plan-related API calls
KEYWORDS = ["quote"]
INSURANCE_NAME = "cholams"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSURER_OUTPUT_DIR = os.path.join(BASE_DIR, "insurer", INSURANCE_NAME)
os.makedirs(INSURER_OUTPUT_DIR, exist_ok=True)
 
def save_claim_response(car_number, response_data, claim_status="not-claimed"):
    if not claim_status:
        return
    filename = f"{car_number}-{claim_status}.json"
    file_path = os.path.join(INSURER_OUTPUT_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(response_data, f, indent=4)
    print(f">>> Saved {claim_status} response to {file_path}")
 
 
 

async def run():

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.grant_permissions(["geolocation"])
        page = await context.new_page()

        # Container to store all captured responses
        captured_data = []

        # --------------------------------------------------
        # LISTEN FOR NETWORK RESPONSES
        # --------------------------------------------------
        def handle_response(response):
            url = response.url.lower()

            if any(k in url for k in KEYWORDS):
                print(f"\n>>> Captured API: {response.url}")

                async def save_json():
                    try:
                        data = await response.json()

                        # Generate file-safe name
                        fname = response.url.split("/")[-1].replace("?", "_")[:60]
                        if not fname.endswith(".json"):
                            fname += ".json"

                        # Save individual API response file using centralized saver
                        save_claim_response(CAR_NUMBER, data, claim_status=f"API_{fname}")
                        print(f"Saved → {INSURER_OUTPUT_DIR}/{CAR_NUMBER}-API_{fname}.json")

                        captured_data.append({
                            "api": response.url,
                            "data": data
                        })

                    except Exception as e:
                        print("JSON parse error:", e)

                asyncio.create_task(save_json())


        # --------------------------------------------------
        # ORIGINAL CHOLA CODE (FULLY PRESERVED)
        # --------------------------------------------------

        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("div.product-container", timeout=30000)

        await page.fill(
            "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-mob-no",
            PHONE
        )

        await page.fill(
            "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-reg-no",
            CAR_NUMBER
        )

        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.click(
                "a#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_quote-btn"
            )

        await page.wait_for_selector(
            "div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto",
            timeout=60000
        )

        await page.click(
            "div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto button.btn.btn-danger.btn-lg"
        )

        await page.wait_for_selector("div.clearfix", timeout=60000)

        await page.wait_for_selector("div.custom-callender input#demo-14", timeout=60000)
        await page.click("div.custom-callender input#demo-14")

        MODAL_SELECTOR = "div.mod-body:has(input#card1)"
        YES_LABEL = f"{MODAL_SELECTOR} label[for='card1']"

        await page.wait_for_selector(MODAL_SELECTOR, timeout=80000, state="visible")
        await page.wait_for_timeout(300)

        await page.wait_for_selector(YES_LABEL, timeout=80000, state="visible")

        print("DEBUG: Clicking label for card1")
        await page.locator(YES_LABEL).click(force=True)
        print("DEBUG: Selected YES radio")

        await page.wait_for_timeout(2000)
        await page.wait_for_load_state("domcontentloaded")

        context.on("response", handle_response)

        # --------------------------------------------------
        # WAIT FOR ALL PREMIUM API CALLS TO FINISH
        # --------------------------------------------------
        print("\n>>> Waiting 10s for premium APIs to complete...")
        await asyncio.sleep(10)

        # --------------------------------------------------
        # SAVE MASTER FILE
        # --------------------------------------------------
        save_claim_response(CAR_NUMBER, captured_data, claim_status="ALL_CHOLA_PREMIUM_APIS")
        print("\n>>> MASTER FILE SAVED in insurer folder ✔")
        print(">>> Total endpoints captured:", len(captured_data))

        await browser.close()


asyncio.run(run())

