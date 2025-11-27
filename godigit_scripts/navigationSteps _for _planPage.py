import asyncio
from playwright.async_api import async_playwright

URL = "https://www.godigit.com/motor-insurance/car-flow/car-plan-page?session=DAGapgHQJmDeqLqxvynWhdSA"

async def scroll_and_click(element):
    await element.scroll_into_view_if_needed()
    await element.click()

async def handle_addons(page):
    add_on_divs = page.locator("div.desktop-idv-content.add-on-wrap")
    count = await add_on_divs.count()
    
    for i in range(count):
        section = add_on_divs.nth(i)
        addon_items = section.locator("div.extra-package-addon")
        item_count = await addon_items.count()
        
        for j in range(item_count):
            addon = addon_items.nth(j)
            checkbox = addon.locator("input[type='checkbox']")
            label = addon.locator("label")
            
            # Click the checkbox
            await scroll_and_click(label)
            
            # Optional: hover on info icon to reveal overlay
            info_icon = addon.locator("div.info-block img")
            if await info_icon.count() > 0:
                await info_icon.hover()
                await page.wait_for_timeout(200)

async def extract_footer(page):
    footer = page.locator("div.footer-card")
    await footer.scroll_into_view_if_needed()
    
    total = await page.locator("#actualPremiumAmount").text_content()
    discounted = await page.locator("#premiumAmount").text_content()
    gst = await page.locator("#gstTextMessage").text_content()
    
    print(f"Footer: Total={total}, Discounted={discounted}, GST={gst}")

async def handle_plan(page, plan):
    # Click the plan checkbox
    checkbox = plan.locator("input[type='checkbox']")
    await scroll_and_click(checkbox)
    
    # Scroll plan info into view
    plan_info = plan.locator("div.plan-info")
    if await plan_info.count() > 0:
        await plan_info.scroll_into_view_if_needed()
    
    # Handle add-ons for this plan
    await handle_addons(page)
    
    # Extract footer info
    await extract_footer(page)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(URL)
        await page.wait_for_load_state("networkidle")
        
        # Get all plan cards
        plan_cards = page.locator("div.plan-card")
        total_plans = await plan_cards.count()
        print(f"Found {total_plans} plans")
        
        for i in range(total_plans):
            plan = plan_cards.nth(i)
            print(f"\n--- Handling plan {i+1}/{total_plans} ---")
            await handle_plan(page, plan)
            await asyncio.sleep(0.5)  # small delay between plans

        await browser.close()

asyncio.run(main())
