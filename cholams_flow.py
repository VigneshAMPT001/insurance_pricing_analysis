import asyncio
from playwright.async_api import async_playwright

CAR_NUMBER = "MH04KW1827"
PHONE = "8325369138"
HOME_URL = "https://www.cholainsurance.com/"

async def click_and_wait_price(page, label_selector):
    # wait for label
    await page.wait_for_selector(label_selector, timeout=60000)

    # try clicking (Angular sometimes blocks first click)
    for _ in range(3):
        try:
            await page.locator(label_selector).click(force=True)
            break
        except:
            await page.wait_for_timeout(400)

    # WAIT for price page to load
    # "p-back" is your given unique price page icon
    await page.wait_for_selector("div.p-back", state="visible", timeout=90000)

    # extra wait for plans to fully load
    await page.wait_for_load_state("networkidle")

    # click back button
    await page.locator("div.p-back").click()

    # wait until you return back to plans list
    await page.wait_for_selector("label.for-checkbox-tools", timeout=60000)
    await page.wait_for_load_state("networkidle")


async def run():

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.grant_permissions(["geolocation"])
        page = await context.new_page()

        # ---- HOME ----
        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("div.product-container")

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

        # ---- GET QUOTE ----
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.click(
                "a#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_quote-btn"
            )

        # ---- VIEW PLAN ----
        await page.wait_for_selector("div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto")
        await page.click(
            "div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto button.btn.btn-danger.btn-lg"
        )

        # ---- MAIN DIV ----
        await page.wait_for_selector("div.clearfix")

        # ---- CALENDAR ----
        await page.click("div.custom-callender input#demo-14")

        # ---- MODAL YES ----
        MODAL_SELECTOR = "div.mod-body:has(input#card1)"
        YES_LABEL = f"{MODAL_SELECTOR} label[for='card1']"

        await page.wait_for_selector(MODAL_SELECTOR, state="visible", timeout=60000)
        await page.wait_for_selector(YES_LABEL, state="visible", timeout=60000)
        await page.locator(YES_LABEL).click(force=True)

        await page.wait_for_timeout(1200)
        await page.wait_for_load_state("networkidle")

        # ---------------------------------------------------
        # 🔥 CLICK PLAN 1 – Comprehensive Cover
        # ---------------------------------------------------
        await click_and_wait_price(
            page,
            "label.for-checkbox-tools:has(div.prod-con.comp)"
        )

        # ---------------------------------------------------
        # 🔥 CLICK PLAN 2 – Zero Dep Cover
        # ---------------------------------------------------
        await click_and_wait_price(
            page,
            "label.for-checkbox-tools:has(div.prod-con.comp-zer)"
        )

        # ---------------------------------------------------
        # 🔥 CLICK PLAN 3 – Third Party Cover
        # ---------------------------------------------------
        await click_and_wait_price(
            page,
            "label.for-checkbox-tools:has(div.prod-con.tp)"
        )


asyncio.run(run())
