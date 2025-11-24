from playwright.async_api import async_playwright
import asyncio
import random


BASE_URL = "https://www.godigit.com/"
REG_NUMBER = "MH04KW1827"
MOBILE_NUMBER = "8765433456"


# -------------------------------------
# CLOUD FLARE TURNSTILE HANDLER
# -------------------------------------
async def wait_for_turnstile_success(page):
    print("🔍 Checking for Cloudflare Turnstile CAPTCHA…")

    try:
        await page.wait_for_selector("iframe[src*='challenges.cloudflare.com']", timeout=8000)
        print("🟡 Turnstile detected — please solve manually.")

        await page.wait_for_function(
            """() => {
                const el = document.querySelector("input[name='cf-turnstile-response']");
                return el && el.value && el.value.length > 20;
            }""",
            timeout=180000
        )

        print("🟢 CAPTCHA solved — token detected.")
    except:
        print("🟢 No Turnstile challenge displayed — continuing.")


# -------------------------------------
# HUMAN LIKE MOVEMENTS
# -------------------------------------
async def human_mouse_wiggle(page):
    for _ in range(3):
        await page.mouse.move(
            random.randint(200, 800),
            random.randint(200, 600),
            steps=random.randint(10, 20)
        )
        await asyncio.sleep(random.uniform(0.2, 0.6))


# -------------------------------------
# MAIN FUNCTION
# -------------------------------------
async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            java_script_enabled=True
        )

        page = await context.new_page()

        # ---------------- OPEN SITE ----------------
        print("🌍 Opening Godigit…")
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await human_mouse_wiggle(page)

        # ---------------- CLICK CAR IMAGE ----------------
        print("🚗 Selecting Car Insurance icon…")
        await page.wait_for_selector("div.qf-switcher-img-holder", timeout=20000)
        await page.click("div.qf-switcher-img-holder")
        await asyncio.sleep(2)

        # ---------------- REGISTRATION LABEL ----------------
        print("🟡 Waiting for Registration Label…")
        await page.wait_for_selector(
            "#car-regstration-input-option label.four-wheeler-form-label",
            timeout=20000
        )

        # ---------------- REGISTRATION INPUT ----------------
        print("🔵 Targeting unique Registration Input Field…")
        reg_input = page.locator("#car-regstration-input-option input[name='registration-search']")

        await reg_input.click()
        await asyncio.sleep(0.3)
        await reg_input.fill(REG_NUMBER)

        print(f"✔ Registration Number Entered: {REG_NUMBER}")
        await asyncio.sleep(1.2)
        await human_mouse_wiggle(page)

        # ---------------- MOBILE NUMBER ----------------
        print("📱 Waiting for Mobile Number section…")
        await page.wait_for_selector("#car-mobile-number-option", timeout=20000)

        print("📱 Filling Mobile Number…")
        mob_input = page.locator("#car-mobile-number-option input#car-mobile-number")
        await mob_input.click()
        await asyncio.sleep(0.3)
        await mob_input.fill(MOBILE_NUMBER)

        print(f"✔ Mobile Number Entered: {MOBILE_NUMBER}")
        await asyncio.sleep(1)

        # ---------------- CLOUDFLARE ----------------
        await wait_for_turnstile_success(page)

        # ---------------- VIEW PRICES ----------------
        print("🔵 Clicking View Prices Button…")
        await page.wait_for_selector("button:has-text('View Prices')", timeout=25000)
        await page.click("button:has-text('View Prices')")

        # ---------------- WAIT FOR PLAN PAGE ----------------
        print("⏳ Waiting for Plan Page…")
        try:
            await page.wait_for_url("**/car-plan-page**", timeout=35000)
            print("🎉 SUCCESS — Reached Plan Page!")
        except:
            print("⚠ Reached next step but URL pattern changed.")

        await asyncio.sleep(5)
        await browser.close()


asyncio.run(main())
