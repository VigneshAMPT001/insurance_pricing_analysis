import asyncio
from playwright.async_api import async_playwright

CAR_NUMBER = "MH04KW1827"
PHONE = "8335278236"

HOME_URL = "https://www.acko.com/?utm_source=google&utm_medium=search&utm_campaign=Brand_NU_Generic_Google_Search_CPC_Chennai_Revenue_Growth_Web"
CAR_URL = "https://www.acko.com/gi/car?utm_source=google&utm_medium=search&utm_campaign=Brand_NU_Generic_Google_Search_CPC_Chennai_Revenue_Growth_Web"

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(">>> Opening Home Page")
        await page.goto(HOME_URL, timeout=60000)

        # ---------------- SELECT CAR INSURANCE ----------------
        print(">>> Selecting Car Insurance")
        await page.wait_for_selector("div.HomeLandingWidget_productCardWrappers__CK_EM")
        
        product_cards = page.locator("div.HomeLandingWidget_productCardWrappers__CK_EM span.ProductCardButton_productHeading__nn6iU")
        count = await product_cards.count()

        for i in range(count):
            text = await product_cards.nth(i).inner_text()
            if "Car" in text or "Car Insurance" in text:
                await product_cards.nth(i).click()
                break

        # ---------------- PAGE 2: ENTER CAR NUMBER ----------------
        print(">>> Waiting for Car Page")
        await page.wait_for_load_state("networkidle")

        print(">>> Filling Registration Number")
        await page.wait_for_selector("input#carNumber")
        await page.fill("input#carNumber", CAR_NUMBER)
        await asyncio.sleep(1)

        # Click 'Check Price'
        print(">>> Clicking Check Price")
        await page.click("button.jsx-2611325737.style-button-primary", timeout=20000)

        # ---------------- PAGE 3: CLAIM QUESTION YES/NO ----------------
        print(">>> Handling Previous Claim Question")
        await page.wait_for_selector("div.jsx-1278309658.question", timeout=50000)

        yes_no_btns = page.locator("button.sc-elJkPf")
        if await yes_no_btns.count() > 0:
            await yes_no_btns.nth(0).click()
        else:
            raise Exception("Could not find Yes/No buttons")

        # ---------------- ENTER PHONE NUMBER ----------------
        print(">>> Entering Phone Number")
        await page.wait_for_selector("input#phone", timeout=30000)
        await page.fill("input#phone", PHONE)
        await asyncio.sleep(1)

        # ---------------- CLICK VIEW PRICES ----------------
        print(">>> Clicking View Prices")
        await page.wait_for_selector("button.sc-eHgmQL.sc-cqpYsc", timeout=20000)
        await page.click("button.sc-eHgmQL.sc-cqpYsc")

        print(">>> Waiting for Price Page...")
        await page.wait_for_load_state("networkidle")

        print(">>> SUCCESS: Landed on plans/pricing page!")
        await asyncio.sleep(10)

        await browser.close()

asyncio.run(run())
