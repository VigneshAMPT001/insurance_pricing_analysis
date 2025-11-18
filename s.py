import asyncio
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

START_URL = "https://www.godigit.com/car-insurance"

PROXY_LIST = [
    {"server": "http://proxy1.example.com:port", "username": "user1", "password": "pass1"},
    {"server": "http://proxy2.example.com:port", "username": "user2", "password": "pass2"},
]

async def launch_browser_with_proxy(playwright, proxy_config):
    browser = await playwright.chromium.launch(
        headless=True,       # RUN IN BACKGROUND
        proxy=proxy_config
    )
    context = await browser.new_context(
        user_agent=random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)"
        ])
    )
    page = await context.new_page()
    return browser, page

async def detect_cloudflare(page):
    try:
        iframe_locator = page.locator(
            'iframe[src*="turnstile"], iframe[src*="cloudflare"], iframe[src*="captcha"]'
        )
        if await iframe_locator.count() > 0:
            print("⚠️ Cloudflare challenge detected!")
            return True

        content = await page.content()
        if "Cloudflare" in content or "captcha" in content.lower():
            print("⚠️ Cloudflare protection detected!")
            return True

    except Exception:
        return False
    return False


async def perform_action_and_view_price(page):
    try:
        print("🟦 Selecting Car Insurance Option...")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1200)

        # Multiple selectors for Car insurance block
        car_selectors = [
            'div.covid-label.car',
            'div.qf-switcher.active',
            'div.qf-switcher-img-holder',
            'text=Car Insurance'
        ]

        for sel in car_selectors:
            try:
                await page.click(sel, timeout=3000)
                break
            except:
                pass

        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight/8)")

        print("🚗 Filling Registration Number...")

        reg_locator = page.locator(
            'input[id*="reg"], input[placeholder*="Register"], input[name*="reg"], input[id*="registration"]'
        )

        await reg_locator.first.fill("MH01DF5698")

        print("📱 Filling Mobile Number...")

        mobile = "8" + "".join(str(random.randint(0, 9)) for _ in range(9))

        mobile_locator = page.locator(
            'input[type="tel"], input[id*="mobile"], input[placeholder*="Mobile"], input[name*="mobile"]'
        )
        await mobile_locator.first.fill(mobile)

        print("🟩 Clicking View Price...")

        view_selectors = [
            'button:has-text("VIEW PRICE")',
            'button:has-text("View Price")',
            'button[id*="view"]',
            'text=View Price'
        ]

        clicked = False
        for btn in view_selectors:
            try:
                await page.click(btn, timeout=5000)
                clicked = True
                break
            except:
                continue

        if not clicked:
            raise Exception("❌ View Price button not found!")

        print("▶️ Navigating to price page...")

        # Wait for next page to load
        await page.wait_for_url("**/car-insurance/**", timeout=30000)

        await page.wait_for_selector(
            'text=Own Damage, text=Zero Dep, div[class*="plan"], div[class*="premium"]',
            timeout=20000
        )

        print("✅ Price Page Loaded Successfully!")

    except PlaywrightTimeoutError:
        print("❌ Timeout waiting for price page.")
    except Exception as e:
        print(f"❌ Error occurred: {e}")


async def main():
    async with async_playwright() as p:

        proxy_index = 0
        proxy_config = PROXY_LIST[proxy_index]

        while True:
            try:
                print(f"🌐 Launching browser with proxy {proxy_config['server']} ...")

                browser, page = await launch_browser_with_proxy(p, proxy_config)

                await page.goto(START_URL, timeout=60000)

                # Check Cloudflare
                if await detect_cloudflare(page):
                    print("🔄 Switching proxy due to CF block...")
                    await browser.close()
                    proxy_index = (proxy_index + 1) % len(PROXY_LIST)
                    proxy_config = PROXY_LIST[proxy_index]
                    continue

                # Execute form automation
                await perform_action_and_view_price(page)

                await asyncio.sleep(5)
                await browser.close()
                break

            except Exception as e:
                print(f"⚠️ Browser crashed or blocked: {e}")
                try:
                    await browser.close()
                except:
                    pass

                proxy_index = (proxy_index + 1) % len(PROXY_LIST)
                proxy_config = PROXY_LIST[proxy_index]

                await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Script interrupted by user. Exiting cleanly...")
