# acko_full_scraper.py
import json
import asyncio
from playwright.async_api import async_playwright


async def safe_get_text(locator):
    try:
        return (await locator.text_content() or "").strip()
    except:
        return None


async def safe_get_attr(locator, attr):
    try:
        return await locator.get_attribute(attr)
    except:
        return None


async def scrape_acko():
    url = "https://www.acko.com/gi/auto-storefront/fresh-car/quote"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)

        scraped = {}

        # -------------------------------------------------------------
        # SECTION 1: IDV DETAILS
        # -------------------------------------------------------------

        # “Your car’s insured value (IDV)”
        idv_title = page.locator(
            'p.sc-cSHVUG.styles__CardHeadingText-sc-h1idlt-1.ejkRwz'
        )
        scraped["idv_title"] = await safe_get_text(idv_title)

        # IDV input box
        idv_input = page.locator('#idv-input-box')
        scraped["idv_value"] = await safe_get_attr(idv_input, "value")

        # Span next to input
        idv_span = page.locator('span.sc-jPPmml.ihflud')
        scraped["idv_span"] = await safe_get_text(idv_span)

        # Slider block: p tags inside sc-bdVaJa.sc-bwzfXH.iUAJNl
        slider_block = page.locator('div#idv-slider-wrapper div.sc-bdVaJa.sc-bwzfXH.iUAJNl')

        scraped["slider_text_1"] = await safe_get_text(
            slider_block.locator('p.sc-cSHVUG.sc-iLVFha.fOSQRJ')
        )

        scraped["slider_text_2"] = await safe_get_text(
            slider_block.locator('p.sc-cgzHhG.bDsDao')
        )

        # Next div sc-bdVaJa.sc-bwzfXH.hWRlh
        block2 = page.locator('div.sc-bdVaJa.sc-bwzfXH.hWRlh')

        scraped["block2_p1"] = await safe_get_text(
            block2.locator('p.sc-cSHVUG.sc-iLVFha.fOSQRJ')
        )
        scraped["block2_span"] = await safe_get_text(
            block2.locator('span.sc-cgzHhG.bDsDao')
        )

        # -------------------------------------------------------------
        # SECTION 2: THREE PLAN DETAILS
        # -------------------------------------------------------------

        # Target 3 plans – class sc-bdVaJa.sc-bwzfXH.sc-kDhYZr.bfAmwl
        plans = page.locator('div.sc-bdVaJa.sc-bwzfXH.sc-kDhYZr.bfAmwl')
        plans_count = await plans.count()

        scraped["plans"] = []

        for i in range(plans_count):
            plan = plans.nth(i)
            garages = await safe_get_text(
                plan.locator("span[style*='text-decoration:underline']")
            )
            scraped["plans"].append({
                "plan_number": i + 1,
                "garages": garages
            })

        # -------------------------------------------------------------
        # SECTION 3: PRICE BLOCKS
        # -------------------------------------------------------------

        # Block sc-bdVaJa.sc-bwzfXH.hjFYAY
        price_block = page.locator('div.sc-bdVaJa.sc-bwzfXH.hjFYAY')
        price_container = price_block.locator('div.sc-bdVaJa.sc-bwzfXH.iUAJNl')

        scraped["price_block_title"] = await safe_get_text(
            price_container.locator('p.sc-cSHVUG.sc-gAmQfK.jFONMz')
        )

        price_p = price_container.locator('p.sc-cSHVUG.sc-cCVOAp.llcldA')
        scraped["price_options_text"] = await safe_get_text(price_p)
        scraped["price_options_value"] = await safe_get_text(price_p.locator("div"))

        # Next block sc-fCPvlr.bfwiTp
        block_fcpv = page.locator('div.sc-fCPvlr.bfwiTp')
        scraped["same_price_title"] = await safe_get_text(
            block_fcpv.locator('p.sc-cSHVUG.sc-gAmQfK.jFONMz')
        )
        same_price_p = block_fcpv.locator('p.sc-cSHVUG.sc-cCVOAp.llcldA')
        scraped["same_price_value"] = await safe_get_text(same_price_p.locator("div"))

        # Footer price sc-bdVaJa.sc-bwzfXH.iVupIy
        footer_block = page.locator('div.sc-bdVaJa.sc-bwzfXH.iVupIy')
        scraped["footer_price"] = await safe_get_text(
            footer_block.locator('p.sc-cSHVUG.styles__FooterPrice-sc-1brs59m-0.fLbRJt')
        )

        # -------------------------------------------------------------
        # SECTION 4: NEXT PAGE SCRAPING
        # -------------------------------------------------------------

        await page.goto(
            "https://www.acko.com/gi/auto-storefront/fresh-car/vehicle-addons/car?proposal_ekey",
            timeout=60000
        )

        addons = {}

        # Recommended heading
        addons["recommended_heading"] = await safe_get_text(
            page.locator('p div.sc-iuJeZd.ioQIDr p.sc-esOvli.kPPQzO')
        )

        # Recommended description
        addons["recommended_description"] = await safe_get_text(
            page.locator(
                'div.jsx-96484109.children-container > p'
            )
        )

        # Addon card wrapper
        addon_cards = page.locator('div.sc-bdVaJa.styles__AddOnCardWrapper-sc-1crp5za-0.bwsaBt')
        count_cards = await addon_cards.count()

        addons["cards"] = []

        for i in range(count_cards):
            card = addon_cards.nth(i)

            card_title = await safe_get_text(
                card.locator('p.sc-cSHVUG.styles__CardHeading-sc-1crp5za-1.ihTnoH')
            )

            bottom_text = await safe_get_text(
                card.locator('p.sc-cSHVUG.styles__AddOnCardBottonText-sc-1crp5za-4.eGaoVQ')
            )

            addons["cards"].append({
                "title": card_title,
                "bottom_text": bottom_text
            })

        scraped["addons"] = addons

        # -------------------------------------------------------------
        # SAVE JSON OUTPUT
        # -------------------------------------------------------------

        with open("acko_scraped.json", "w", encoding="utf-8") as f:
            json.dump(scraped, f, indent=4, ensure_ascii=False)

        print("\nSCRAPING COMPLETED. Saved → acko_scraped.json\n")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_acko())
