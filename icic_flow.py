import asyncio
import json
from playwright.async_api import async_playwright

HOME_URL = "https://www.icicilombard.com/"
CAR_NUMBER = "MH12SE5466"
MOBILE = "8534678225"
EMAIL = "surbhii255@gmail.com"

# Keywords to detect ANY premium/plan API
KEYWORDS = ["premium", "plan", "quote", "addon", "coverage"]

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Storage container for ALL premium API responses
        api_responses = []

        print(">>> Opening Website Fast")
        await page.goto(HOME_URL, timeout=60000)

        # ------------------------------------------------------
        # LISTEN FOR **ALL NETWORK RESPONSES**
        # ------------------------------------------------------
        def handle_response(response):
            url = response.url.lower()

            if any(k in url for k in KEYWORDS):
                print(f"\n>>> Captured API: {response.url}")

                async def save_json():
                    try:
                        data = await response.json()

                        # Save individual file
                        fname = response.url.split("/")[-1].replace("?", "_")[:50]
                        if not fname.endswith(".json"):
                            fname += ".json"

                        with open(f"api_{fname}", "w") as f:
                            json.dump(data, f, indent=4)

                        print(f"Saved → api_{fname}")

                        api_responses.append({
                            "api": response.url,
                            "data": data
                        })

                    except:
                        pass

                asyncio.create_task(save_json())

        context.on("response", handle_response)

        # ------------------------------------------------------
        # START QUOTE PROCESS → THIS TRIGGERS MANY APIS
        # ------------------------------------------------------
        print(">>> Clicking Car Tab")
        await page.locator("div.tabSectionImg span:has-text('Car')").click()

        print(">>> Filling Form")
        await page.locator("#valid-carregnumber").fill(CAR_NUMBER)
        await page.locator("#valid-mobilenumber").fill(MOBILE)
        await page.locator("#valid-emailid").fill(EMAIL)

        print(">>> Clicking Get Quote")
        await page.locator("#car-get-quote").click()

        # ------------------------------------------------------
        # WAIT FOR ALL PREMIUM API CALLS TO FIRE
        # ------------------------------------------------------
        print(">>> Waiting for ALL premium APIs to load (10 seconds)...")
        await asyncio.sleep(10)

        # ------------------------------------------------------
        # SAVE MASTER JSON
        # ------------------------------------------------------
        with open("ALL_PREMIUM_RESPONSES.json", "w") as f:
            json.dump(api_responses, f, indent=4)

        print("\n\n>>> MASTER FILE SAVED: ALL_PREMIUM_RESPONSES.json ✔")
        print(">>> Total premium API captured:", len(api_responses))

        await browser.close()


asyncio.run(run())
