import asyncio
import os
import json
from pathlib import Path
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page
from icic_bs4_scraper import (
    extract_idv_values,
    extract_icici_car_details,
    scrape_icic_plan_premium,
    scrape_icic_plans,
)

HOME_URL = "https://www.icicilombard.com/"
CAR_NUMBER = "MH04KW1827"
MOBILE = "8514646225"
EMAIL = "vignesh27@gmail.com"

# Keywords to detect ANY premium/plan API
KEYWORDS = ["premium", "plan", "quote", "addon", "coverage"]


async def locate_plan_buttons(page: Page):
    selectors = [
        ".plans-box button",  # typical
        "button.plans-box",  # button itself has class
        ".singlecard button",  # inside single card
        "app-plan-card button",  # Angular app plan cards
    ]

    for sel in selectors:
        els = await page.locator(sel).all()
        if els:
            return els

    return []


async def process_plan_buttons_without_radio(page: Page):
    results = []
    plan_buttons = await locate_plan_buttons(page)

    for idx in range(len(plan_buttons)):
        button = await refresh_button(page, idx)
        text = (await button.inner_text()).strip()[:50]

        try:
            await button.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        except:
            continue

        html = await page.content()
        scraped = scrape_icic_plans(html)

        results.append(
            {
                "plan_type": None,
                "plan_type_index": None,
                "button_index": idx,
                "button_text": text,
                "scraped_data": scraped,
            }
        )

    return results


async def refresh_button(page: Page, index: int):
    selectors = [
        ".plans-box button",
        "button.plans-box",
        "app-plan-card button",
        ".singlecard button",
    ]

    for sel in selectors:
        loc = page.locator(sel)
        count = await loc.count()
        if count > index:
            return loc.nth(index)

    return None


async def get_all_plans(page: Page):
    print("\n>>> Locating plan type radio buttons...")
    # Count them (NEVER store node handles!)
    total_radio_groups = await page.locator("div.il-radio-group").count()
    print(f">>> Total plan types found = {total_radio_groups}")
    return total_radio_groups


async def reveal_addons_cover(page: Page):
    # Click all <a> tags inside <span.down-arrow> to reveal add cover details, if present
    try:
        down_arrows = await page.query_selector_all("span.down-arrow a.js_showaddCover")
        for arrow in down_arrows:
            try:
                await arrow.click(force=True)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Could not click one down-arrow: {e}")
    except Exception as e:
        print(f"Error finding down-arrow to show add cover: {e}")


async def dismiss_vehicle_inspection_model(page: Page):
    try:
        popup_selector = "div.car-panel-content.bg-white.active"
        ok_button_selector = "a.ui-close-slide.triggerClick.ng-star-inserted"

        # Check if popup exists & is visible
        if await page.locator(popup_selector).is_visible(timeout=3000):
            print(">>> 'Vehicle Inspection' popup detected. Clicking Ok to proceed...")

            await page.locator(ok_button_selector).click(force=True)

            # Wait for popup to disappear
            await page.wait_for_selector(popup_selector, state="hidden", timeout=10000)
            print(">>> Vehicle Inspection popup dismissed.")
    except Exception as e:
        print(f">>> No Vehicle Inspection popup detected or error occurred: {e}")


async def click_through_plan_types_and_buttons(page: Page) -> List[Dict[str, Any]]:
    """
    Stable scraper:
    - Iterates plan type radio buttons
    - For each plan type, iterates plan buttons
    - Extracts HTML for every combination
    """
    plans = []
    premiums = []
    scraped_plans = {}

    total_radio_groups = await get_all_plans(page)

    await dismiss_vehicle_inspection_model(page)

    await reveal_addons_cover(page)

    # ----------------------------------------------------------------------
    # OUTER LOOP: PLAN TYPES
    # ----------------------------------------------------------------------

    for radio_idx in range(total_radio_groups):

        # -------- RE-QUERY fresh locator (DOM-safe) ----------
        radio_group = page.locator("div.il-radio-group").nth(radio_idx)
        radio_input = radio_group.locator("input[type='radio']")
        label = radio_group.locator("label")

        # Extract label text
        try:
            label_text = (await label.inner_text()).strip()
        except:
            label_text = f"Plan Type {radio_idx+1}"

        print(
            f"\n>>> === PLAN TYPE {radio_idx+1}/{total_radio_groups}: {label_text} ==="
        )

        # ---------------------------------------------------
        # CLICK PLAN TYPE RADIO BUTTON
        # ---------------------------------------------------
        try:
            is_checked = await radio_input.is_checked()

            if is_checked:
                print(f">>> Already selected: {label_text}")
            else:
                print(f">>> Clicking plan type: {label_text}")
                await radio_input.click(force=True)
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(1)
        except Exception as e:
            print(f">>> Failed to select plan type '{label_text}': {e}")
            continue

        html_plan_details = await get_html(page)  # page.content()

        scraped_plans[label_text] = scrape_icic_plans(html_plan_details)
        plans.append(scraped_plans)

        # ----------------------------------------------------------------------
        # INNER LOOP: CLICK EACH PLAN BUTTON FOR THIS PLAN TYPE
        # ----------------------------------------------------------------------
        plan_buttons = await locate_plan_buttons(page)

        if not plan_buttons:
            print(f">>> No plan buttons found for {label_text}")
            continue

        print(
            f">>> Found {len(plan_buttons)} plan buttons under plan type '{label_text}'"
        )

        button_count = len(plan_buttons)

        for btn_idx in range(button_count):

            # RE-LOCATE the button fresh (DOM-safe)
            button = await refresh_button(page, btn_idx)

            if button is None:
                print(f">>> Button {btn_idx+1} missing after refresh, skipping.")
                continue

            # Extract label safely
            try:
                button_text = (await button.inner_text()).strip()[:50]
            except:
                button_text = f"Plan Button {btn_idx+1}"

            print(f">>> Clicking plan button {btn_idx+1}/{button_count}: {button_text}")

            # -----------------------------
            # CLICK THE BUTTON
            # -----------------------------
            try:
                await button.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(1)
            except Exception as e:
                print(f">>> Error clicking plan button: {e}")
                continue

            # -----------------------------
            # SCRAPE HTML
            # -----------------------------
            html_premium_expanded = await get_html(page)  # page.content()

            premium_data = scrape_icic_plan_premium(html_premium_expanded)

            premiums.append(
                {
                    "plan_type": label_text,
                    "plan_type_index": radio_idx,
                    "button_index": btn_idx,
                    "button_text": button_text,
                    "premium": premium_data,
                }
            )

            print(f">>> ✔ Scraped: {label_text} - {button_text}")

    plan_data = {"plans": plans, "premiums": premiums}
    return plan_data


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

                # api_responses.append({"api": response.url, "data": data})

            except:
                pass

        asyncio.create_task(save_json())


async def dismiss_initial_vehicle_inspection(page: Page):
    # If "Vehicle Inspection" popup is present, click the Ok button before proceeding
    try:
        # Wait for either the popup or main content to appear, do not block too long
        popup_selector = "div#break-case-odpolicy.js-popup-wrap.active"
        ok_button_selector = f"{popup_selector} .primary-btn"

        # Check if the popup is visible
        if await page.locator(popup_selector).is_visible(timeout=3000):
            print(">>> 'Vehicle Inspection' popup detected. Clicking Ok to proceed...")
            await page.locator(ok_button_selector).click()
            # Wait for popup to disappear before proceeding
            await page.wait_for_selector(popup_selector, state="hidden", timeout=10000)
            print(">>> Vehicle Inspection popup dismissed.")
    except Exception as e:
        print(f">>> No Vehicle Inspection popup detected or error occurred: {e}")


async def open_close_idv_popup(page: Page, car_details: Dict):
    updated_details = car_details.copy()
    try:
        # --- Min/Max IDV ---
        edit_button = page.locator(
            "div.idv-range-slider", has_text="Insured declared value"
        ).locator("a.link-btn")
        await edit_button.click(force=True)

        html_idv_popup = await get_html(page)

        # Copy car_details to avoid mutating the input dictionary
        recommended, min_idv, max_idv = extract_idv_values(html_idv_popup)
        updated_details["idv"] = recommended
        updated_details["idv_min"] = min_idv
        updated_details["idv_max"] = max_idv

        await page.locator("#idvPopup a.close.js-popup-close.triggerClick").click()

    except Exception as e:
        print(f">>> Error opening/closing IDV popup: {e}")
        return updated_details

    return updated_details


async def get_html(page: Page) -> str:
    return await page.content()


async def run():
    output_path = Path("extracted/icici")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Storage container for ALL premium API responses
        # api_responses = []

        print(">>> Opening Website Fast")
        await page.goto(HOME_URL, timeout=60000)

        # ------------------------------------------------------
        # LISTEN FOR **ALL NETWORK RESPONSES**
        # ------------------------------------------------------

        # context.on("response", handle_response)

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
        # WAIT FOR PAGE TO LOAD AFTER GET QUOTE
        # ------------------------------------------------------
        print(">>> Waiting for page to load...")
        await page.wait_for_load_state("networkidle", timeout=30000)

        await dismiss_initial_vehicle_inspection(page)

        await page.wait_for_timeout(10000)

        html_car_details = await get_html(page)  # page.content()

        car_details = extract_icici_car_details(html_car_details)

        car_details = await open_close_idv_popup(page, car_details)

        # ------------------------------------------------------
        # CLICK THROUGH PLAN TYPES AND BUTTONS
        # ------------------------------------------------------
        print(">>> Starting plan type and button clicking flow...")
        plans = await click_through_plan_types_and_buttons(page)

        car_details["plans_offered"] = plans

        # ------------------------------------------------------
        # SAVE ALL SCRAPED DATA
        # ------------------------------------------------------
        output_file = f"{output_path}/{CAR_NUMBER}-not_claimed.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(car_details, f, indent=4, ensure_ascii=False)
        print(f">>> All scraped data saved to: {output_file} ✔")

        # ------------------------------------------------------
        # SAVE HTML FOR BS4 SCRAPING (FINAL STATE)
        # ------------------------------------------------------
        # print(">>> Saving final HTML page for bs4 scraping...")
        # html_content = await page.content()
        # with open(f"{output_file.strip(".json")}.html", "w", encoding="utf-8") as f:
        #     f.write(html_content)
        # print(">>> HTML saved → icic_quote_page.html ✔")

        # ------------------------------------------------------
        # SAVE MASTER JSON
        # ------------------------------------------------------
        # with open("ALL_PREMIUM_RESPONSES.json", "w") as f:
        #     json.dump(api_responses, f, indent=4)

        # print("\n\n>>> MASTER FILE SAVED: ALL_PREMIUM_RESPONSES.json ✔")
        # print(">>> Total premium API captured:", len(api_responses))

        await browser.close()


asyncio.run(run())
