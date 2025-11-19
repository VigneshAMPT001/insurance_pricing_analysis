import asyncio
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
CAR_NUMBER = "MH04KW1827"
PHONE = "8325369138"
HOME_URL = "https://www.cholainsurance.com/"

async def run():

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.grant_permissions(["geolocation"])
        page = await context.new_page()

        # ---- OPEN HOME PAGE ----
        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("div.product-container", timeout=30000)

        # ---- ENTER MOBILE ----
        await page.fill(
            "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-mob-no",
            PHONE
        )

        # ---- ENTER REG NUMBER ----
        await page.fill(
            "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-reg-no",
            CAR_NUMBER
        )

        # ---- CLICK GET QUOTE ----
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.click(
                "a#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_quote-btn"
            )

        # ---- CLICK VIEW PLAN ----
        await page.wait_for_selector(
            "div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto",
            timeout=60000
        )

        await page.click(
            "div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto button.btn.btn-danger.btn-lg"
        )

        # ---- WAIT FOR MAIN DIV ----
        await page.wait_for_selector("div.clearfix", timeout=60000)

        # ---- CLICK CALENDAR ----
        await page.wait_for_selector("div.custom-callender input#demo-14", timeout=60000)
        await page.click("div.custom-callender input#demo-14")

        # ---- TARGET ONLY THE MODAL THAT CONTAINS CARD1 RADIO ----
        MODAL_SELECTOR = "div.mod-body:has(input#card1)"
        YES_LABEL = f"{MODAL_SELECTOR} label[for='card1']"

        # Wait for modal to appear
        await page.wait_for_selector(MODAL_SELECTOR, timeout=80000, state="visible")

        # Small delay for animation
        await page.wait_for_timeout(300)

        print("DEBUG: Correct modal is visible")

        # Wait for label (radio button UI) to be clickable
        await page.wait_for_selector(YES_LABEL, timeout=80000, state="visible")

        # Debug label text
        label_el = await page.query_selector(YES_LABEL)
        if label_el:
            txt = await label_el.inner_text()
            print("DEBUG: Label text:", repr(txt))
        else:
            print("DEBUG: Label not found:", YES_LABEL)

        # ---- CLICK THE RADIO BUTTON BY CLICKING LABEL ----
        print("DEBUG: Clicking label for card1")
        await page.locator(YES_LABEL).click(force=True)
        print("DEBUG: Selected YES radio option")


        # Allow modal to close fully
        await page.wait_for_timeout(2000)

        # Ensure next page loads
        await page.wait_for_load_state("domcontentloaded")


asyncio.run(run())
