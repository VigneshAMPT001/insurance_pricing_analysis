import asyncio
import json
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page
from icic_bs4_scraper import scrape_icic_plans

HOME_URL = "https://www.icicilombard.com/"
CAR_NUMBER = "MH04KW1827"
MOBILE = "8534675225"
EMAIL = "surbhi55@gmail.com"

# Keywords to detect ANY premium/plan API
KEYWORDS = ["premium", "plan", "quote", "addon", "coverage"]


async def click_through_plan_types_and_buttons(page: Page) -> List[Dict[str, Any]]:
    """
    Click through all buttons in plans-box, then for each button, loop through all plan type radio buttons.
    Extract and scrape HTML for each combination.

    Args:
        page: Playwright page object

    Returns:
        List of dictionaries containing scraped data for each combination
    """
    all_scraped_data = []

    # -------------------------------------------------------------
    # FIND ALL BUTTONS INSIDE "plans-box" (OUTER LOOP)
    # -------------------------------------------------------------
    print("\n>>> Finding all buttons inside 'plans-box'...")

    # Try multiple selectors for plans-box
    plans_box_selector = ".plans-box, button.plans-box, .singlecard"
    plan_buttons = await page.locator(plans_box_selector).all()

    if not plan_buttons:
        print(f">>> No buttons found with selector '{plans_box_selector}'")
        # Try to get the plans-box container and find buttons inside it
        plans_box_container = page.locator(".plans-box").first
        if await plans_box_container.count() > 0:
            plan_buttons = await plans_box_container.locator("button").all()
        else:
            # Try app-plan-card approach
            plan_buttons = await page.locator(
                "app-plan-card button, app-plan-card .plans-box"
            ).all()

    if not plan_buttons:
        print(">>> No plan buttons found")
        return all_scraped_data

    print(f">>> Found {len(plan_buttons)} buttons in plans-box")

    # -------------------------------------------------------------
    # FIND ALL RADIO BUTTONS MATCHING PATTERN
    # Pattern: <div class="il-radio-group ...">
    #           <input type="radio" id="checkOdtpCaseValue" ...>
    #           <label for="checkOdtpCaseValue">Own Damage</label>
    #          </div>
    # -------------------------------------------------------------
    print("\n>>> Finding all plan type radio buttons...")
    radio_groups = await page.locator("div.il-radio-group").all()

    if not radio_groups:
        print(">>> No radio buttons found with class 'il-radio-group'")
        # Still try to process plan buttons without radio buttons
        radio_groups = []

    print(f">>> Found {len(radio_groups)} radio button groups")

    # -------------------------------------------------------------
    # ITERATE THROUGH PLAN BUTTONS (OUTER LOOP)
    # -------------------------------------------------------------
    for btn_idx, button in enumerate(plan_buttons):
        try:
            # Get button text/identifier
            button_text = f"Button {btn_idx + 1}"
            if await button.count() > 0:
                button_text = await button.inner_text()
            button_text = button_text.strip()[:50]  # Limit length

            print(
                f"\n>>> Processing plan button {btn_idx + 1}/{len(plan_buttons)}: {button_text}"
            )

            # -------------------------------------------------------------
            # ITERATE THROUGH PLAN TYPES (INNER LOOP)
            # -------------------------------------------------------------
            if not radio_groups:
                # No radio buttons found, just click the plan button and scrape
                print(f">>> Clicking button: {button_text}")
                await button.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(1)

                plans_box_html = await extract_plans_box_html(page)
                if plans_box_html:
                    scraped = scrape_icic_plans(plans_box_html)
                    all_scraped_data.append(
                        {
                            "button_index": btn_idx,
                            "button_text": button_text,
                            "plan_type": None,
                            "plan_type_index": None,
                            "scraped_data": scraped,
                        }
                    )
                continue

            for radio_idx, radio_group in enumerate(radio_groups):
                try:
                    # Get the radio input and label
                    radio_input = radio_group.locator("input[type='radio']")
                    label = radio_group.locator("label")

                    # Check if radio is already checked
                    is_checked = await radio_input.is_checked()

                    # Get label text
                    label_text = f"Plan Type {radio_idx + 1}"
                    if await label.count() > 0:
                        label_text = await label.inner_text()

                    print(
                        f">>> Processing plan type {radio_idx + 1}: {label_text.strip()}"
                    )

                    # If first radio (Comprehensive) is auto-selected, skip clicking it
                    if radio_idx == 0 and is_checked:
                        print(
                            f">>> Plan type '{label_text.strip()}' is already selected (auto-selected), skipping click"
                        )
                    else:
                        # Click the radio button
                        print(f">>> Clicking radio button for: {label_text.strip()}")
                        await radio_input.click()

                        # Wait for network to be idle after clicking
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await asyncio.sleep(1)  # Small wait to ensure UI updates

                    # -------------------------------------------------------------
                    # CLICK THE PLAN BUTTON
                    # -------------------------------------------------------------
                    print(f">>> Clicking plan button: {button_text}")
                    await button.click()

                    # Wait for network to be idle
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await asyncio.sleep(1)  # Small wait to ensure UI updates

                    # -------------------------------------------------------------
                    # EXTRACT HTML SECTION FOR plans-box
                    # -------------------------------------------------------------
                    plans_box_html = await extract_plans_box_html(page)

                    if plans_box_html:
                        # -------------------------------------------------------------
                        # SCRAPE WITH BEAUTIFULSOUP
                        # -------------------------------------------------------------
                        scraped = scrape_icic_plans(plans_box_html)

                        all_scraped_data.append(
                            {
                                "button_index": btn_idx,
                                "button_text": button_text,
                                "plan_type": label_text.strip(),
                                "plan_type_index": radio_idx,
                                "scraped_data": scraped,
                            }
                        )

                        print(
                            f">>> Scraped data for button '{button_text}', plan type '{label_text.strip()}'"
                        )
                    else:
                        print(
                            f">>> Could not extract plans-box HTML for button '{button_text}', plan type '{label_text.strip()}'"
                        )

                except Exception as e:
                    print(f">>> Error processing radio group {radio_idx + 1}: {e}")
                    continue

        except Exception as e:
            print(f">>> Error clicking plan button {btn_idx + 1}: {e}")
            continue

    return all_scraped_data


async def extract_plans_box_html(page: Page) -> str:
    """
    Extract HTML content for the plans-box section.

    Args:
        page: Playwright page object

    Returns:
        HTML string of the plans-box section, or empty string if not found
    """
    try:
        # Try to find plans-box container
        plans_box = page.locator(".plans-box").first

        if await plans_box.count() > 0:
            return await plans_box.inner_html()

        # Try app-plan-card container
        app_plan_card = page.locator("app-plan-card").first
        if await app_plan_card.count() > 0:
            return await app_plan_card.inner_html()

        # Try to find the plans container by other selectors
        plans_container = page.locator(".singlecard, .plans-box-container").first
        if await plans_container.count() > 0:
            return await plans_container.inner_html()

        # If nothing found, return the whole page content (fallback)
        # But try to narrow down to the main content area
        main_content = page.locator(
            "app-select-plans-components, app-select-plans-page"
        ).first
        if await main_content.count() > 0:
            return await main_content.inner_html()

        # Final fallback: return empty
        return ""

    except Exception as e:
        print(f">>> Error extracting plans-box HTML: {e}")
        return ""


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

                        api_responses.append({"api": response.url, "data": data})

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
        output_file = "icic_scraped_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_scraped_data, f, indent=4, ensure_ascii=False)
        print(f">>> All scraped data saved to: {output_file} ✔")
        print(f">>> Total plan type combinations scraped: {len(all_scraped_data)}")

        # ------------------------------------------------------
        # SAVE HTML FOR BS4 SCRAPING (FINAL STATE)
        # ------------------------------------------------------
        print(">>> Saving final HTML page for bs4 scraping...")
        html_content = await page.content()
        with open("icic_quote_page.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(">>> HTML saved → icic_quote_page.html ✔")

        # ------------------------------------------------------
        # SAVE MASTER JSON
        # ------------------------------------------------------
        # with open("ALL_PREMIUM_RESPONSES.json", "w") as f:
        #     json.dump(api_responses, f, indent=4)

        print("\n\n>>> MASTER FILE SAVED: ALL_PREMIUM_RESPONSES.json ✔")
        print(">>> Total premium API captured:", len(api_responses))

        await browser.close()


asyncio.run(run())
