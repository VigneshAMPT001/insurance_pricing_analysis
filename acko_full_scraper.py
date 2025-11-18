import json
import asyncio
from playwright.async_api import async_playwright

CAR_NUMBER = "MH04KW1827"
PHONE = "8335278236"

HOME_URL = "https://www.acko.com/"
CAR_URL = "https://www.acko.com/gi/car"


# -------------------------------------------------------------------
# SAFE HELPERS
# -------------------------------------------------------------------
async def safe_get_text(locator):
    try:
        val = await locator.text_content()
        return (val or "").strip()
    except:
        return None


async def safe_get_attr(locator, attr):
    try:
        return await locator.get_attribute(attr)
    except:
        return None


# -------------------------------------------------------------------
# MAIN SCRAPER
# -------------------------------------------------------------------
async def scrape_acko_full_flow():

    final_json = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ---------------------------------------------------------
        # STEP 1: HOME PAGE → CAR INSURANCE
        # ---------------------------------------------------------
        print(">>> Opening Home")
        await page.goto(HOME_URL, timeout=60000)

        await page.wait_for_selector("div.HomeLandingWidget_productCardWrappers__CK_EM")

        product_cards = page.locator(
            "div.HomeLandingWidget_productCardWrappers__CK_EM span.ProductCardButton_productHeading__nn6iU"
        )

        count = await product_cards.count()
        for i in range(count):
            name = await product_cards.nth(i).inner_text()
            if "Car" in name:
                print(">>> Clicking Car Insurance")
                await product_cards.nth(i).click()
                break

        # ---------------------------------------------------------
        # STEP 2: ENTER CAR NUMBER
        # ---------------------------------------------------------
        print(">>> Waiting for Car Page...")
        await page.wait_for_load_state("networkidle")

        await page.wait_for_selector("input#carNumber")
        print(">>> Filling Car Number")
        await page.fill("input#carNumber", CAR_NUMBER)
        await asyncio.sleep(1)

        print(">>> Clicking Check Price")
        await page.click("button.jsx-2611325737.style-button-primary")

        # ---------------------------------------------------------
        # STEP 3: PREVIOUS CLAIM → YES/NO
        # ---------------------------------------------------------
        print(">>> Handling Claim Question")
        await page.wait_for_selector("div.jsx-1278309658.question")

        yes_no = page.locator("button.sc-elJkPf")
        await yes_no.nth(0).click()  # Click YES

        # ---------------------------------------------------------
        # STEP 4: ENTER PHONE
        # ---------------------------------------------------------
        print(">>> Entering Phone")
        await page.wait_for_selector("input#phone")
        await page.fill("input#phone", PHONE)

        print(">>> Clicking View Prices")
        await page.click("button.sc-eHgmQL.sc-cqpYsc")

        # ---------------------------------------------------------
        # STEP 5: LAND ON PRICING PAGE
        # ---------------------------------------------------------
        print(">>> Waiting for Pricing Page")
        await page.wait_for_selector("p.sc-cSHVUG.styles__CardHeadingText-sc-h1idlt-1.ejkRwz", timeout=60000)

        print(">>> Scraping Pricing Page...")

        # ---------------------------------------------------------
        # PRICING PAGE SCRAPE START
        # ---------------------------------------------------------
        scraped = {}

        idv_title = page.locator("p.sc-cSHVUG.styles__CardHeadingText-sc-h1idlt-1.ejkRwz")
        scraped["idv_title"] = await safe_get_text(idv_title)

        idv_input = page.locator("#idv-input-box")
        scraped["idv_value"] = await safe_get_attr(idv_input, "value")

        idv_span = page.locator("span.sc-jPPmml.ihflud")
        scraped["idv_span"] = await safe_get_text(idv_span)

        # Three plans
        plans = page.locator("div.sc-bdVaJa.sc-bwzfXH.sc-kDhYZr.bfAmwl")
        count = await plans.count()
        scraped["plans"] = []

        for i in range(count):
            garages = await safe_get_text(
                plans.nth(i).locator("span[style*='text-decoration:underline']")
            )
            scraped["plans"].append({
                "plan_number": i + 1,
                "garages": garages
            })

        # Footer Price
        footer = page.locator("div.sc-bdVaJa.sc-bwzfXH.iVupIy p.sc-cSHVUG.styles__FooterPrice-sc-1brs59m-0.fLbRJt")
        scraped["footer_price"] = await safe_get_text(footer)

        final_json["price_page"] = scraped

        # ---------------------------------------------------------
        # STEP 6: NAVIGATE TO ADDONS PAGE
        # ---------------------------------------------------------
        print(">>> Going to Addons page...")
        await page.goto("https://www.acko.com/gi/auto-storefront/fresh-car/vehicle-addons/car?proposal_ekey", timeout=60000)

        addons = {}
        addons["recommended_heading"] = await safe_get_text(
            page.locator("p div.sc-iuJeZd.ioQIDr p.sc-esOvli.kPPQzO")
        )

        addons["recommended_description"] = await safe_get_text(
            page.locator("div.jsx-96484109.children-container > p")
        )

        addon_cards = page.locator("div.sc-bdVaJa.styles__AddOnCardWrapper-sc-1crp5za-0.bwsaBt")
        cnt = await addon_cards.count()

        addons["cards"] = []
        for i in range(cnt):
            card = addon_cards.nth(i)
            title = await safe_get_text(card.locator("p.sc-cSHVUG.styles__CardHeading-sc-1crp5za-1.ihTnoH"))
            bottom = await safe_get_text(card.locator("p.sc-cSHVUG.styles__AddOnCardBottonText-sc-1crp5za-4.eGaoVQ"))

            addons["cards"].append({
                "title": title,
                "bottom_text": bottom
            })

        final_json["addons"] = addons

        # ---------------------------------------------------------
        # FINAL SAVE
        # ---------------------------------------------------------
        with open("acko_full_output.json", "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4)

        print("\n>>> DONE: Saved → acko_full_output.json\n")

        await browser.close()


# RUN
if __name__ == "__main__":
    asyncio.run(scrape_acko_full_flow())
