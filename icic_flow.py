import asyncio
import json
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page
from icic_bs4_scraper import (
    extract_car_details,
    scrape_icic_plan_premium,
    scrape_icic_plans,
)

HOME_URL = "https://www.icicilombard.com/"
CAR_NUMBER = "MH04KW1827"
MOBILE = "8534675225"
EMAIL = "surbhi55@gmail.com"

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


async def click_through_plan_types_and_buttons(page: Page) -> List[Dict[str, Any]]:
    """
    Stable scraper:
    - Iterates plan type radio buttons
    - For each plan type, iterates plan buttons
    - Extracts HTML for every combination
    """
    all_scraped_data = []

    car_data = await extract_car_details(page)

    all_scraped_data["car_details"] = car_data

    print("\n>>> Locating plan type radio buttons...")

    # Count them (NEVER store node handles!)
    total_radio_groups = await page.locator("div.il-radio-group").count()
    print(f">>> Total plan types found = {total_radio_groups}")

    # # ----------------------------------------------------------------------
    # # If NO RADIO BUTTONS -> directly scrape plan buttons (fallback mode)
    # # ----------------------------------------------------------------------
    # if total_radio_groups == 0:
    #     print(">>> No radio plan types found. Processing plan buttons directly...")
    #     return await process_plan_buttons_without_radio(page)

    # # ---------------------------------------------------------------
    # # TEST CLICK RADIO BUTTONS (to ensure they are clickable)
    # # ---------------------------------------------------------------
    # print("\n>>> Performing test-click pass for all radio buttons...")

    # for test_idx in range(total_radio_groups):

    #     # Re-locate fresh (DOM-safe)
    #     test_radio_group = page.locator("div.il-radio-group").nth(test_idx)
    #     test_radio_input = test_radio_group.locator("input[type='radio']")
    #     test_label = test_radio_group.locator("label")

    #     try:
    #         label = (await test_label.inner_text()).strip()
    #     except:
    #         label = f"Radio {test_idx+1}"

    #     print(f">>> Test-clicking radio {test_idx+1}/{total_radio_groups}: {label}")

    #     try:
    #         await test_radio_input.click(force=True)
    #         await page.wait_for_load_state("networkidle")
    #         await asyncio.sleep(10)
    #     except Exception as e:
    #         print(f"!!! FAILED to test-click radio {label}: {e}")

    # print(">>> Test-click pass complete.\n")

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
                await asyncio.sleep(2)
        except Exception as e:
            print(f">>> Failed to select plan type '{label_text}': {e}")
            continue

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
        html = await page.content()

        scraped_plans = scrape_icic_plans(html)
        all_scraped_data.append(scraped_plans)

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
                await asyncio.sleep(2)
            except Exception as e:
                print(f">>> Error clicking plan button: {e}")
                continue

            # Click all <a> tags inside <span.down-arrow> to reveal add cover details, if present
            try:
                down_arrows = await page.query_selector_all(
                    "span.down-arrow a.js_showaddCover"
                )
                for arrow in down_arrows:
                    try:
                        await arrow.click()
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Could not click one down-arrow: {e}")
            except Exception as e:
                print(f"Error finding down-arrow to show add cover: {e}")
            # -----------------------------
            # SCRAPE HTML
            # -----------------------------

            premium_data = scrape_icic_plan_premium(html)

            all_scraped_data.append(
                {
                    "plan_type": label_text,
                    "plan_type_index": radio_idx,
                    "button_index": btn_idx,
                    "button_text": button_text,
                    "premium": premium_data,
                }
            )

            print(f">>> ✔ Scraped: {label_text} - {button_text}")

    return all_scraped_data


async def run():
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
        await asyncio.sleep(3)  # Extra wait to ensure dynamic content loads

        # If "Vehicle Inspection" popup is present, click the Ok button before proceeding
        try:
            # Wait for either the popup or main content to appear, do not block too long
            popup_selector = "div#break-case-odpolicy.js-popup-wrap.active"
            ok_button_selector = f"{popup_selector} .primary-btn"

            # Check if the popup is visible
            if await page.locator(popup_selector).is_visible(timeout=3000):
                print(
                    ">>> 'Vehicle Inspection' popup detected. Clicking Ok to proceed..."
                )
                await page.locator(ok_button_selector).click()
                # Wait for popup to disappear before proceeding
                await page.wait_for_selector(
                    popup_selector, state="hidden", timeout=10000
                )
                print(">>> Vehicle Inspection popup dismissed.")
        except Exception as e:
            print(f">>> No Vehicle Inspection popup detected or error occurred: {e}")
        # ------------------------------------------------------
        # CLICK THROUGH PLAN TYPES AND BUTTONS
        # ------------------------------------------------------
        print(">>> Starting plan type and button clicking flow...")
        all_scraped_data = await click_through_plan_types_and_buttons(page)

        # ------------------------------------------------------
        # SAVE ALL SCRAPED DATA
        # ------------------------------------------------------
        output_file = f"icic_scraped_output_{CAR_NUMBER}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_scraped_data, f, indent=4, ensure_ascii=False)
        print(f">>> All scraped data saved to: {output_file} ✔")
        print(f">>> Total plan type combinations scraped: {len(all_scraped_data)}")

        # ------------------------------------------------------
        # SAVE HTML FOR BS4 SCRAPING (FINAL STATE)
        # ------------------------------------------------------
        # print(">>> Saving final HTML page for bs4 scraping...")
        # html_content = await page.content()
        # with open("icic_quote_page.html", "w", encoding="utf-8") as f:
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
