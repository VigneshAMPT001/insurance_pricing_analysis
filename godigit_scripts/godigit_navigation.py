from playwright.async_api import async_playwright
import asyncio
import random

BASE_URL = "https://www.godigit.com/"
CAR_NUMBER = "MH04KW1827"
MOBILE = "8" + "".join(str(random.randint(0,9)) for _ in range(9))


async def main():
    print(f"📱 Using mobile: {MOBILE}")

    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        print("🌍 Opening website...")
        await page.goto(BASE_URL, wait_until="domcontentloaded")

        print("🚗 Navigating to Car Insurance...")
        await page.click('a[href*="car-insurance"]', timeout=15000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        print("\n🟡 Filling Registration Number...")
        reg = page.locator("input[placeholder*='E.g'], input[placeholder*='Registration']")
        await reg.click()
        await reg.fill(CAR_NUMBER)
        print("✔ Registration number entered")

        print("\n🟡 Filling Mobile Number...")
        mob = page.locator("input[type='tel']")
        await mob.click()
        await mob.fill(MOBILE)
        print("✔ Mobile number entered")

        print("\n⏳ Waiting for CAPTCHA to be solved by user...")
        # Wait until the captcha box gets class "checked"
        await page.wait_for_selector("iframe[src*='cloudflare']", timeout=20000)

        # Wait for success token
        await context.wait_for_event("requestfinished", timeout=0)

        print("🟢 Detected CAPTCHA iframe. Please tick the CAPTCHA manually...")

        # Wait for validation checkmark in DOM
        await page.wait_for_selector("text=verified", timeout=None)
        print("✔ CAPTCHA solved by user")

        print("\n🔵 Clicking View Prices button...")
        await page.click("button:has-text('View Prices')")

        print("⏳ Waiting for next page...")
        try:
            await page.wait_for_url("**/car-plan-page**", timeout=30000)
            print("🎉 SUCCESS: Reached Plan Page!")
        except:
            print("⚠ Page changed but URL match failed (may still be OK).")

        await asyncio.sleep(5)
        await browser.close()

asyncio.run(main())
