import asyncio
import json
from pathlib import Path
from pprint import pprint
from playwright.async_api import async_playwright

from chola_bs4_scraper import (
    parse_car_details,
    parse_premium_breakup,
    parse_cover_sections,
    parse_idv_section,
)

CAR_NUMBER = "MH04KW1827"
PHONE = "8325349135"
HOME_URL = "https://www.cholainsurance.com/"


async def clear_backdrop(page):
    # Remove backdrop if present
    backdrops = page.locator("div.modal-backdrop.show")
    if await backdrops.count() > 0:
        print("Backdrop found → removing it")
        await page.evaluate(
            """
            document.querySelectorAll('.modal-backdrop.show')
                .forEach(el => el.remove());
            document.body.classList.remove('modal-open');
            document.body.style.overflow = 'auto';
        """
        )
        await page.wait_for_timeout(300)


async def click_plans_with_back(page):

    async def clear_backdrop(page):
        try:
            await page.evaluate(
                """() => {
                    const el = document.querySelector('.modal-backdrop');
                    if (el) el.remove();
                }"""
            )
            await page.wait_for_timeout(500)
        except:
            pass

    # re-locate the back button fresh every time
    async def do_back_click():
        back_btn = page.locator("div.p-back img")

        # Make sure it is visible
        await page.wait_for_selector("div.p-back img", timeout=8000)
        await back_btn.scroll_into_view_if_needed()
        await click_force_js(back_btn)

    async def click_force_js(locator):
        try:
            await locator.click(timeout=2000)
        except:
            try:
                box = await locator.bounding_box()
                if box:
                    await page.mouse.click(
                        box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                    )
                    return
            except:
                pass

            # Final fallback
            try:
                handle = await locator.element_handle()
                if handle:
                    await page.evaluate("(el) => el.click()", handle)
            except:
                pass

    # Clean leftover modal blockers
    await clear_backdrop(page)

    plans_data = []

    plans = page.locator("div.covet-type")
    tit_divs = page.locator("div.tit")

    tit_count = await tit_divs.count()
    for i in range(tit_count):
        print(await tit_divs.nth(i).inner_text())

    count = await plans.count()
    print("plans count", count)

    i = 0
    while i < count:

        # --- PLAN LIST PAGE ---

        plan = plans.nth(i)

        plan_title_locator = plan.locator("div.tit")
        plan_title = await plan_title_locator.inner_text()
        print("\n=== PLAN:", plan_title, "===")
        plan_obj = {}
        plan_obj[plan_title] = {}

        clickable = plan.locator("div.prod-con")
        await clickable.scroll_into_view_if_needed()

        print(f"Clicking plan {i+1}/{count}")
        await click_force_js(clickable)

        # --- DETAILS PAGE ---

        # Ensure details page is fully loaded
        await clear_backdrop(page)

        await page.locator("div.prem-break span", has_text="Premium Breakup").click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3000)

        # Wait for the modal to appear after clicking "Premium Breakup" before getting HTML
        await page.wait_for_selector("div.modal-content", timeout=5000)
        premium_html = await page.content()
        plan_details = {}
        plan_details["plan_premium"] = parse_premium_breakup(premium_html)
        plan_details["idv_range"] = parse_idv_section(premium_html)

        await page.locator("div.mod-close button.btn-close").click()

        await page.wait_for_timeout(2000)

        await page.locator("div.cover-more", has_text="Know More").click()

        covers_html = await page.content()
        plan_details["benefits_covered"] = parse_cover_sections(covers_html)

        pprint(plan_details)
        what_covers_close_btn = page.locator("div#knowmorenew button.btn-close")
        await what_covers_close_btn.scroll_into_view_if_needed()
        await what_covers_close_btn.click(force=True)

        plan_obj[plan_title] = plan_details

        # --- GO BACK ---
        await page.wait_for_selector("div.p-back img", timeout=10000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(5000)

        plans_data.append(plan_obj)

        print("Going BACK...")

        # main attempt
        await do_back_click()
        if i == 1:
            await do_back_click()

        # Wait for list page
        try:
            await page.wait_for_selector("div.box.pro-sel", timeout=10000)
        except:
            print("⚠ Back didn't work, retrying…")
            await clear_backdrop(page)
            await page.wait_for_timeout(500)
            await do_back_click()
            await page.wait_for_selector("div.box.pro-sel", timeout=10000)

        i += 1

    print("Done visiting all plans.")

    return plans_data


async def run():

    output_path = Path("extracted/cholams")
    output_path.mkdir(parents=True, exist_ok=True)

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
            PHONE,
        )

        # ---- ENTER REG NUMBER ----
        await page.fill(
            "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-reg-no",
            CAR_NUMBER,
        )

        # ---- GET QUOTE ----
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.click(
                "a#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_quote-btn"
            )

        # ---- VIEW PLAN ----
        await page.wait_for_selector(
            "div.d-grid.gap-2.col-lg-12.col-md-12.col-sm-12.mx-auto"
        )
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

        print("opening modal")

        await page.wait_for_selector(MODAL_SELECTOR, state="visible", timeout=60000)
        await page.wait_for_selector(YES_LABEL, state="visible", timeout=60000)
        await page.locator(YES_LABEL).click(force=True)

        base_html = await page.content()
        car_details = parse_car_details(base_html)

        print("calling plan clicker")

        # await page.wait_for_load_state("networkidle")

        plans_data = await click_plans_with_back(page)
        plans_obj = {}
        plans_obj["plans"] = plans_data
        car_details.append(plans_data)
        file_name = output_path / f"{CAR_NUMBER}-claimed.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(car_details, f, indent=2)
        print(f"Output written to: {file_name}")


asyncio.run(run())
