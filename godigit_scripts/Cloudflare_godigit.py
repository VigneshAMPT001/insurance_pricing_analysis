import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://www.godigit.com/"
CAR_NUMBER = "MH04  KW  1827"  # Registration number with spaces as requested
MOBILE = "8712345645"

async def wait_for_cloudflare(page):
    print("🛡 Checking Cloudflare…")
    try:
        await page.wait_for_selector("iframe[title='Widget containing a Cloudflare security challenge']", timeout=5000)
        print("⚠️ Cloudflare challenge detected — waiting…")
        await page.wait_for_timeout(8000)
    except:
        print("✔️ No Cloudflare challenge.")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("🌍 Opening website…")
        await page.goto(BASE_URL, timeout=60000)
        await wait_for_cloudflare(page)

        print("🚗 Clicking Car Insurance…")
        await page.click("a[href='/car-insurance']", timeout=15000)
        await wait_for_cloudflare(page)

        print("🟡 Selecting Registration Input…")
        reg_input = page.locator("input[name='carRegistrationNumber']")
        await reg_input.wait_for(state="visible")
        await reg_input.click()
        await reg_input.fill("")
        await reg_input.type(CAR_NUMBER)

        print("📱 Filling Mobile Number…")
        mobile_input = page.locator("input[name='mobileNumber']")
        await mobile_input.wait_for(state="visible")
        await mobile_input.click()
        await mobile_input.type(MOBILE)

        print("▶️ Clicking Get Quote…")
        await page.click("button:has-text('Get Quote')")

        await wait_for_cloudflare(page)

        print("⏳ Waiting for results page…")
        await page.wait_for_load_state('networkidle')
        print("✔️ Done.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
