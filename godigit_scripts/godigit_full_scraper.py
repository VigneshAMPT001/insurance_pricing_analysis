#!/usr/bin/env python3
import asyncio
from operator import sub
from pathlib import Path
from datetime import datetime
from pandas.core.dtypes.dtypes import time
from playwright.async_api import Page, async_playwright
from godigit_bs4 import (
    handle_claim_ncb_and_ownership,
    parse_comprehensive_plan_footer,
    scrape_idv_block,
    scrape_plan_card,
    scrape_policy_durations,
    scrape_plan_info,
    extract_extra_addons,
    extract_ncb_percentage_and_value,
    extract_addon_names,
    extract_policy_durations,
    parse_trust_card_numbers_only,
    parse_popular,
    parse_popular_pack,
    parse_addon_pack,
    extract_cost_breakup,
    extract_idv_values,
)


# ----------------- CONFIG -----------------
BASE_URL = "https://www.godigit.com/"
REG_NO = "MH12VZ2302"
MOBILE = "8712347645"

OUTPUT_DIR = Path("extracted/godigit")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
delete navigator.__proto__.webdriver;
"""


async def click_force_js(page, locator):
    for attempt in range(5):
        try:
            await locator.click(timeout=2000)
            return True
        except Exception:
            pass
        try:
            box = await locator.bounding_box()
            if box:
                await page.mouse.click(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                )
                return True
        except Exception:
            pass
        try:
            handle = await locator.element_handle()
            if handle:
                await page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            pass
        await page.wait_for_timeout(500)
    return False


async def fill_force_js(page, locator, value):
    try:
        await locator.fill(value)
        return
    except Exception:
        pass
    try:
        handle = await locator.element_handle()
        if handle:
            # set value and dispatch events
            await page.evaluate(
                """
                (el, val) => {
                  el.value = val;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """,
                handle,
                value,
            )
    except Exception:
        pass


async def clear_backdrop(page):
    try:
        await page.evaluate(
            """
        document.querySelectorAll('.modal-backdrop.show').forEach(e => e.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = 'auto';
        """
        )
        await page.wait_for_timeout(300)
    except Exception:
        pass


async def wait_for_cloudflare(page, timeout_s=30):
    for _ in range(timeout_s):
        html = (await page.content()).lower()
        if "checking your browser" not in html:
            return True
        if await page.locator("#car-tab").count() > 0:
            return True
        await page.wait_for_timeout(1000)
    print("⚠ Cloudflare check timeout")
    return False


def ts():
    return datetime.utcnow().isoformat().replace(":", "-").split(".")[0]


# ----------------- Page actions -----------------


async def click_car_insurance_tab(page):
    print("[1] Clicking Car Insurance tab…")
    tab = page.locator("#car-tab")
    await page.wait_for_timeout(500)
    await click_force_js(page, tab)
    await page.wait_for_timeout(1000)


async def fill_registration_number(page):
    print("[2] Filling vehicle registration…")
    try:
        locator = page.locator("input#car-registration-number")
        await locator.wait_for(timeout=15000)
        await fill_force_js(page, locator, REG_NO)
        return
    except Exception:
        pass
    try:
        textbox = page.get_by_role("textbox", name="E.g. KA04DK8337")
        await fill_force_js(page, textbox, REG_NO)
    except Exception:
        print("❌ Could not find registration input.")


async def fill_mobile_number(page):
    print("[3] Filling mobile number…")
    try:
        locator = page.locator("#mobile")
        await locator.wait_for(timeout=15000)
        await fill_force_js(page, locator, MOBILE)
        return
    except Exception:
        pass
    try:
        textbox = page.get_by_role("textbox", name="Enter Mobile Number")
        await fill_force_js(page, textbox, MOBILE)
    except Exception:
        print("❌ Could not find mobile input.")


async def click_view_prices(page):
    print("[4] Clicking View Prices…")
    btn = page.locator("button#get-quote-btn[ng-click*='carWheelerCtrl']")
    if await btn.count() == 0:
        try:
            btn = page.get_by_role("button", name="View Prices").filter(
                has=page.locator("[ng-click*='carWheelerCtrl']")
            )
        except Exception:
            pass
    try:
        await btn.wait_for(state="attached", timeout=15000)
    except Exception:
        print("⚠ View Prices button not present/attached")
    try:
        el_handle = await btn.element_handle()
        await page.wait_for_function(
            """(el) => el && !el.disabled && !el.classList.contains('btn-loading')""",
            arg=el_handle,
            timeout=15000,
        )
    except Exception:
        print("⚠ Button stayed disabled; proceeding anyway")
    try:
        await page.evaluate(
            "(el) => el.scrollIntoView({behavior:'instant', block:'center'})",
            await btn.element_handle(),
        )
    except Exception:
        pass
    await clear_backdrop(page)
    clicked = await click_force_js(page, btn)
    if clicked:
        print("[5] View Prices clicked")
        await page.wait_for_timeout(1500)
        return True
    print("❌ Could not click 'View Prices'.")
    return False


async def handle_km_modal(page):
    print("[6] Checking for KM modal…")
    try:
        km_modal = page.locator(".sticky.motor-question-modal")
        await km_modal.wait_for(state="visible", timeout=15000)
        km_option = km_modal.locator(
            "input.kmRangeRadio[value='0-4000 km (0-10 km/day)']"
        )
        await click_force_js(page, km_option)
        submit_btn = km_modal.locator("button:has-text('Continue')")
        if await submit_btn.count() > 0:
            await click_force_js(page, submit_btn)
            await page.wait_for_timeout(800)
        print("[7] KM modal answered")
    except Exception:
        print("⚠ KM modal not found — continuing…")


# async def wait_for_plan_page(page):
#     print("[8] Waiting for Plan Page to load…")
#     # Combined selectors that may represent the plan list / plan cards
#     plan_section = page.locator(".plans-container, .plan-cards, .plan-cards-wrapper")
#     try:
#         await plan_section.first.wait_for(state="visible", timeout=45000)
#         await page.wait_for_load_state("networkidle")
#         print("[9] Plan page loaded!")
#     except Exception:
#         print("⚠ Plan page did not load in time")
#         await clear_backdrop(page)
#     return plan_section


# ----------------- NEW BLOCK YOU REQUESTED -----------------


async def handle_pa_owner_cover(page):
    print("[A] Handling PA Owner Cover…")

    section = page.locator(
        "#pa-cover.extra-package-addon.pa-owner-cover-section.d-block.package-addon-pa-owner"
    )
    await section.wait_for(timeout=20000)

    checkbox = section.locator(
        "input#paOwner.ng-tns-c136-2.ng-star-inserted[value='1500000.02']"
    )

    # Find the label for the checkbox
    label = section.locator("label[for='paOwner']")

    # Check: if the label has a ::after pseudo element, consider it as selected
    label_after_content = await page.evaluate(
        """
        (el) => {
            const style = window.getComputedStyle(el, '::after');
            return style && style.content && style.content !== "none";
        }
        """,
        await label.element_handle(),
    )
    if label_after_content:
        print(
            "  - PA Owner Cover already selected (label has ::after). Skipping click."
        )
        return

    # Fallback: Skip if already checked
    if await checkbox.is_checked():
        print("  - PA Owner Cover already selected (checkbox). Skipping click.")
        return

    await click_force_js(page, checkbox)

    # wait premium update
    await page.wait_for_timeout(5000)


async def handle_idv_edit_icon(page):
    print("[B] Handling IDV and Edit Icons…")

    # stable selector
    idv_edit_container = page.locator("div.idv-content-container.edit-idv-container")
    await idv_edit_container.wait_for(timeout=3000)

    # Check if already in edit mode (input box present)
    edit_input = idv_edit_container.locator("input[type='text'], input[type='number']")
    if await edit_input.count() > 0:
        print("  - Already in edit mode. Skipping click.")
        return

    # Otherwise, click on the visible text
    await idv_edit_container.get_by_text("Edit").click()
    await page.wait_for_timeout(500)


# async def handle_select_modal(page):
#     print("[C] Clicking Select & Modal Options…")

#     select_btn = page.locator("button:has-text('Select')")
#     await click_force_js(page, select_btn)
#     await page.wait_for_timeout(1500)

#     modal = page.locator(".ng-tns-c60-45")
#     await modal.wait_for(timeout=20000)

#     radio = modal.locator(".zdPopUpRadioButton.mr-3.ng-tns-c136-2.previousZdOpt")
#     await click_force_js(page, radio)

#     await page.wait_for_timeout(5000)  # wait premium update


async def extract_ncb_protect(page: Page):
    # -----------------------------
    # Extract Label + Price
    # -----------------------------

    # Extract subcover label (example: "Same NCB Slab")
    sub_label = await page.locator(
        "div.ncb-protect-cover-section.active p.text-xs.text-grey-800"
    ).inner_text()

    # Extract price text (example: "₹698")
    price = await page.locator(
        "div.ncb-protect-cover-section.active p.font-bold.text-grey-800.text-base"
    ).inner_text()

    print(f"  - Sub-cover Label: {sub_label.strip()}")
    print(f"  - Price: {price.strip()}")

    return {"ncb_protection": {sub_label: price}}


async def handle_ncb_addon(page: Page):
    print("[D] Handling NCB Protector Add-on…")

    # Main add-on label
    ncb_label = page.locator("label#ncb-protector[for='ncb-protector-addon']")
    ncb_checkbox = page.locator("input#ncb-protector-addon")
    await ncb_label.scroll_into_view_if_needed()

    # -----------------------------
    # Skip click if already selected
    # -----------------------------

    # Check using ::after
    has_after = await page.evaluate(
        """(label) => {
            const style = window.getComputedStyle(label, '::after');
            return style && style.content && style.content !== 'none' && style.content !== '';
        }""",
        await ncb_label.element_handle(),
    )
    if has_after:
        print("  - Already selected (via ::after). Skipping.")
        return await extract_ncb_protect(page)

    # Check using checkbox
    if await ncb_checkbox.is_checked():
        print("  - Already selected (checkbox). Skipping.")
        return await extract_ncb_protect(page)

    # -----------------------------
    # Activate the add-on
    # -----------------------------
    await ncb_label.click(force=True)
    print("  - NCB Protector Add-on selected.")
    await page.wait_for_timeout(4000)
    return await extract_ncb_protect(page)


async def select_ultimate_addon_package(page: Page):
    try:
        print("[C] Selecting ultimate addon package…")

        addons_container = page.locator("div#packageAddonCards")

        await addons_container.wait_for(state="visible", timeout=10000)

        await addons_container.scroll_into_view_if_needed()

        # Wait until container exists
        addons_container = page.locator("div#packageAddonCards")
        await addons_container.wait_for(timeout=10000)

        # Find all packages inside
        addon_packages = addons_container.locator(
            "div.package-addon-section.add-on-list"
        )

        # Ensure the list is actually rendered
        await addon_packages.first.wait_for(timeout=5000)

        # Select last package
        last_package = addon_packages.last
        addon_html = await last_package.inner_html()
        addons_details = parse_addon_pack(addon_html)
        await last_package.scroll_into_view_if_needed()

        select_btn = last_package.locator("div.editIcon.select-btn:not(.remove-btn)")

        # Scroll + click
        # await click_force_js(page, select_btn)
        await select_btn.click(force=True)

        # click yes for previous zd cover in the modal
        # Wait for the 'Yes' button in the modal, then click it
        zd_modal_button = page.locator("div.zdPopUpRadioButton.previousZdOpt")
        await zd_modal_button.wait_for(state="visible", timeout=10000)
        yes_btn = zd_modal_button.locator("a")
        await yes_btn.click(force=True)

        # print("Selected the ultimate addon package.")

        await page.wait_for_timeout(5000)

        return addons_details

    except Exception as e:
        print(f"⚠ Error selecting the ultimate addon package: {e}")


async def select_all_addons(page: Page):
    addon_items = page.locator("div.add-on-list .extra-package-addon")

    addons_extender = page.locator("div.addon-card-extend")
    if await addons_extender.count() > 0:
        await addons_extender.scroll_into_view_if_needed()
        await addons_extender.click(force=True)

    count = await addon_items.count()
    print(f"Found {count} addons")

    addons = []  # to store extracted data

    for i in range(count):
        item = addon_items.nth(i)
        await item.scroll_into_view_if_needed()

        checkbox = item.locator("input[type='checkbox']")
        label = item.locator("label")
        title = await item.locator(".checkbox-label").inner_text()

        # Extract addon details, with price as value or "N/A" if not present
        price_val = (
            await item.locator(".price").inner_text()
            if await item.locator(".price").count() > 0
            else "N/A"
        )
        addon_info = {
            "id": await checkbox.get_attribute("id"),
            "label": await item.locator(".checkbox-label").inner_text(),
            "price": price_val,
        }
        addons.append(addon_info)

        # Check if already selected
        is_checked = await checkbox.is_checked()
        if is_checked:
            print(f"Skipping '{title}' — already checked")
            continue

        # Scroll, click, and wait a bit
        await label.scroll_into_view_if_needed()
        await label.click(force=True)

        print(f"Clicked addon: {title}")

        await page.wait_for_timeout(15000)  # wait before next click

    print("All addons processed.")
    return addons


async def click_continue_btn(page: Page):
    """
    Clicks the 'Continue' button to proceed to the next page.
    Uses JS force click fallback if needed.
    """
    try:
        await page.wait_for_load_state(state="load", timeout=3000)
        print("[*] Trying to click continue button to proceed...")
        continue_btn_to_next_page = page.locator("button#continue-btn")
        await continue_btn_to_next_page.scroll_into_view_if_needed()
        await click_force_js(page, continue_btn_to_next_page)
        print("[✔] Clicked continue button successfully.")

        modal_confirm_continue = page.locator("button.vehicle-details-submit")
        await click_force_js(page, modal_confirm_continue)
    except Exception as e:
        print(f"[!] Could not click continue button: {e}")


async def click_back_breadcrumb(page: Page):
    """
    Clicks the back arrow 'a' tag in the breadcrumb section.
    """
    try:
        print("[*] Clicking breadcrumb back arrow...")
        # Target the 'a' tag by its combination of classes (or the presence of inner img)
        breadcrumb_a = page.locator(
            "div.choose-details-bredcrumb a.cursor-pointer.tab-key-border"
        )
        await breadcrumb_a.wait_for(state="visible", timeout=5000)
        await click_force_js(page, breadcrumb_a)
        print("[✔] Clicked the breadcrumb back arrow.")
        return True
    except Exception as e:
        print(f"[!] Could not click the breadcrumb back arrow: {e}")
        return False


# ----------------- MASTER FUNCTION TO RUN ALL -----------------


async def run_additional_steps(page: Page, go_back):
    plan_data = {}
    plan_details = {}
    initial_html = await page.content()
    plan_card = scrape_plan_card(initial_html)
    plan_name = plan_card.get("plan_name", "default")
    locator = page.locator("div.add-on-list")

    found = True
    try:
        # Try with a small timeout, does NOT block long
        await locator.wait_for(timeout=2000)
    except Exception:
        found = False

    if found:
        print("[**] Found add-on-wrap → selecting standard addons")
        await locator.scroll_into_view_if_needed()
        td_addons = await select_all_addons(page)
        plan_details["addons"] = td_addons

    else:
        print("[**] No add-on-wrap → selecting ultimate addon package")
        addon_data = await select_ultimate_addon_package(page)
        await handle_pa_owner_cover(page)
        await handle_idv_edit_icon(page)
        ncb_protection = await handle_ncb_addon(page)
        await page.wait_for_timeout(10000)

        plan_details["addons"] = addon_data if addon_data else {}
        if ncb_protection:
            plan_details["addons"].update(ncb_protection)

    plan_details["idv"] = scrape_idv_block(initial_html)
    plan_details["plan_card"] = plan_card
    # Gather all the data under the plan_name key
    await click_continue_btn(page)
    await page.wait_for_timeout(10000)
    plan_details["premium_breakup"] = await extract_cost_breakup(page)

    # Store under main details dict with plan_name as the main key
    plan_data[plan_name] = plan_details
    # await handle_select_modal(page)
    print("[✔] All extra steps completed")
    print("\n=== Aggregated details ===")
    print(plan_data)
    if go_back:
        await click_back_breadcrumb(page)
    return plan_data


async def iterate_over_plans(page: Page):
    await page.wait_for_load_state(timeout=10000)
    plans = []
    overall_data = {}
    plans_container = page.locator("div#planCards")
    plan_cards = plans_container.locator("div.plan-card")
    total_plans_count = await plan_cards.count()

    ncb_details = await handle_claim_ncb_and_ownership(page)

    should_go_back = True
    for i in range(total_plans_count):
        # Click the i-th plan card before running additional steps
        plan_card = plan_cards.nth(i)
        await plan_card.scroll_into_view_if_needed()
        await plan_card.click(force=True)
        await page.wait_for_timeout(4000)
        plan_data = await run_additional_steps(page, should_go_back)
        plans.append(plan_data)

    overall_data["ncb_status"] = ncb_details
    overall_data["plans_offered"] = plans
    return overall_data


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )  # set headless=True if desired
        context = await browser.new_context()
        page = await context.new_page()

        # Stealth script injection
        try:
            await page.add_init_script(STEALTH_JS)
        except Exception:
            pass

        print("Navigating to base url...")
        await page.goto(BASE_URL)
        await wait_for_cloudflare(page)

        # Interact with the initial form
        try:
            await click_car_insurance_tab(page)
        except Exception as e:
            print(f"⚠ Could not click car tab: {e}")
        await fill_registration_number(page)
        await fill_mobile_number(page)
        view_ok = await click_view_prices(page)
        if not view_ok:
            print("Exiting due to inability to click View Prices.")
            await browser.close()
            return

        await handle_km_modal(page)

        # Wait for plan page to load
        # await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(20000)

        all_plans_data = await iterate_over_plans(page)

        # Write the plans data to a JSON file only if there is data
        if all_plans_data and len(all_plans_data.get("plans_offered")) > 0:
            output_path = OUTPUT_DIR / f"{REG_NO}-not_claimed.json"
            with open(output_path, "w", encoding="utf-8") as f:
                import json

                json.dump(all_plans_data, f, ensure_ascii=False, indent=2)
            print(f"Plans data written to {output_path}")
        else:
            print("No plans data found. Skipping file write.")

        await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting.")
