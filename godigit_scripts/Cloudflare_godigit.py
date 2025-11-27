import asyncio
import sys
from playwright.async_api import async_playwright

BASE_URL = "https://www.godigit.com/"
REG_NO = "MH04KW1827"
MOBILE = "8712345645"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
delete navigator.__proto__.webdriver;
"""

# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

async def click_force_js(page, locator):
    """Robust click → normal → mouse → JS fallback"""
    for attempt in range(5):
        try:
            await locator.click(timeout=2000)
            return True
        except:
            pass
        try:
            box = await locator.bounding_box()
            if box:
                await page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                return True
        except:
            pass
        try:
            handle = await locator.element_handle()
            if handle:
                await page.evaluate("(el) => el.click()", handle)
                return True
        except:
            pass
        await page.wait_for_timeout(500)
    return False


async def fill_force_js(page, locator, value):
    """Fill input robustly with JS fallback"""
    try:
        await locator.fill(value)
        return
    except:
        pass
    try:
        handle = await locator.element_handle()
        if handle:
            await page.evaluate("(el, val) => el.value = val", handle, value)
    except:
        pass


async def clear_backdrop(page):
    """Remove modal/backdrop if present"""
    try:
        await page.evaluate("""
            document.querySelectorAll('.modal-backdrop.show').forEach(e => e.remove());
            document.body.classList.remove('modal-open');
            document.body.style.overflow = 'auto';
        """)
        await page.wait_for_timeout(300)
    except:
        pass

# Wait for either Cloudflare to finish OR a key element to appear
async def wait_for_cloudflare(page):
    for _ in range(30):
        html = (await page.content()).lower()
        if "checking your browser" not in html:
            return True
        if await page.locator("#car-tab").count() > 0:
            return True
        await page.wait_for_timeout(1000)
    print("⚠ Cloudflare check timeout")
    return False




# ---------------------------------------------------------
# Steps
# ---------------------------------------------------------

async def click_car_insurance_tab(page):
    print("🚗 Clicking Car Insurance tab…")
    tab = page.locator("#car-tab")
    await page.wait_for_timeout(500)
    await click_force_js(page, tab)
    await page.wait_for_timeout(1000)


async def fill_registration_number(page):
    print("📌 Filling vehicle registration…")
    try:
        locator = page.locator("input#car-registration-number")
        await locator.wait_for(timeout=15000)
        await fill_force_js(page, locator, REG_NO)
        return
    except:
        pass
    try:
        textbox = page.get_by_role("textbox", name="E.g. KA04DK8337")
        await fill_force_js(page, textbox, REG_NO)
    except:
        print("❌ Could not find registration input.")


async def fill_mobile_number(page):
    print("📱 Filling mobile number…")
    try:
        locator = page.locator("#mobile")
        await locator.wait_for(timeout=15000)
        await fill_force_js(page, locator, MOBILE)
        return
    except:
        pass
    try:
        textbox = page.get_by_role("textbox", name="Enter Mobile Number")
        await fill_force_js(page, textbox, MOBILE)
    except:
        print("❌ Could not find mobile input.")


async def click_view_prices(page):
    """Click the 'View Prices' CTA once form validation enables it"""
    print("💰 Clicking View Prices…")
    btn = page.locator("button#get-quote-btn[ng-click*='carWheelerCtrl']")
    if await btn.count() == 0:
        # Fallback to accessible name filter if Angular attribute changes
        btn = page.get_by_role("button", name="View Prices").filter(
            has=page.locator("[ng-click*='carWheelerCtrl']")
        )
    await btn.wait_for(state="attached", timeout=15000)

    # Wait until Angular enables the button (ng-disabled=false)
    try:
        await page.wait_for_function(
            """(el) => el && !el.disabled && !el.classList.contains('btn-loading')""",
            arg=await btn.element_handle(),
            timeout=15000
        )
    except:
        print("⚠ Button stayed disabled; proceeding anyway")

    # Bring the button into view and clear any overlays before clicking
    try:
        await page.evaluate(
            "(el) => el.scrollIntoView({behavior:'instant', block:'center'})",
            await btn.element_handle()
        )
    except:
        pass
    await clear_backdrop(page)

    clicked = await click_force_js(page, btn)
    if clicked:
        print("✔ View Prices clicked")
        await page.wait_for_timeout(1500)
        return True

    print("❌ Could not click 'View Prices'.")
    return False


async def handle_km_modal(page):
    print("📌 Checking for KM modal…")
    try:
        km_modal = page.locator(".sticky.motor-question-modal")
        await km_modal.wait_for(state="visible", timeout=15000)
        km_option = km_modal.locator("input.kmRangeRadio[value='0-4000 km (0-10 km/day)']")
        await click_force_js(page, km_option)
        submit_btn = km_modal.locator("button:has-text('Continue')")
        if await submit_btn.count() > 0:
            await click_force_js(page, submit_btn)
        await page.wait_for_timeout(800)
        print("✔ KM modal answered")
    except:
        print("⚠ KM modal not found — continuing…")


# ---------------------------------------------------------
# Main runner
# ---------------------------------------------------------

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        await page.add_init_script(STEALTH_JS)

        # ---- Open website ----
        print("🌍 Opening GoDigit…")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await wait_for_cloudflare(page)
        await clear_backdrop(page)

        # ---- Select Car Insurance Tab ----
        await click_car_insurance_tab(page)
        await clear_backdrop(page)

        # ---- Fill Registration + Mobile ----
        await fill_registration_number(page)
        await fill_mobile_number(page)
        # await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(10000)
        

        # ---- Click View Prices (robust retry) ----
        clicked = await click_view_prices(page)
        if not clicked:
            await browser.close()
            sys.exit(1)  # Stop script immediately if View Prices not clicked

        # ---- Handle KM modal ----
        await handle_km_modal(page)

        # ---- Wait for Plan Page (DOM-based) ----
        print("🚀 Waiting for Plan Page to load…")
        plan_section = page.locator(".plans-container, .plan-cards, .plan-cards-wrapper")
        try:
            await plan_section.first.wait_for(state="visible", timeout=45000)
            await page.wait_for_load_state("networkidle")
            print("✔ Plan page loaded!")
        except:
            print("⚠ Plan page did not load in time")
        await clear_backdrop(page)

        # ---- Optional: Click first plan ----
        try:
            first_plan_btn = plan_section.locator("button:has-text('Select Plan')").first
            await click_force_js(page, first_plan_btn)
            print("✔ First plan selected!")
        except:
            print("⚠ Could not select a plan")

        # Keep browser open for inspection
        await page.wait_for_timeout(8000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
