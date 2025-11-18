import asyncio
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
CAR_NUMBER = "MH04KW1827"
PHONE = "8325369138"
HOME_URL = "https://www.cholainsurance.com/"

async def run():
    """
    Automates the process of selecting Car Insurance, filling in mobile and
    registration details, and clicking the 'GET QUOTE' button on the Chola website.
    """
    async with async_playwright() as pw:
        # Launch browser in non-headless mode for visual inspection
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # ---------------- STEP 1: OPEN HOME PAGE ----------------
        print(f">>> Opening Home Page: {HOME_URL}")
        # Use 'domcontentloaded' for initial fast navigation
        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for the main product container to stabilize
        await page.wait_for_selector("div.product-container", timeout=30000)

        # # ---------------- STEP 2: SELECT CAR INSURANCE ----------------
        # print(">>> Selecting Car Insurance")
        
        # # Target the 'Car' tab using its unique ID, which also contains the onclick action
        # CAR_TAB_SELECTOR = "a#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_tab-car"
        
        # await page.wait_for_selector(CAR_TAB_SELECTOR)
        # await page.click(CAR_TAB_SELECTOR)
        # print(">>> Car Insurance tab clicked successfully.")

        # ---------------- STEP 3: ENTER MOBILE NUMBER ----------------
        print(">>> Entering Mobile Number")
        
        # Target the mobile input field using its unique ID
        MOBILE_INPUT_SELECTOR = "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-mob-no"
        
        await page.wait_for_selector(MOBILE_INPUT_SELECTOR, state='visible', timeout=30000)
        await page.fill(MOBILE_INPUT_SELECTOR, PHONE)
        print(f">>> Mobile Number filled: {PHONE}")
        await asyncio.sleep(0.5) # Slight pause to simulate user input

        # ---------------- STEP 4: ENTER REGISTRATION NUMBER ----------------
        print(">>> Entering Registration Number")
        
        # Target the registration input field using its unique ID
        REG_NO_INPUT_SELECTOR = "input#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_insurance-reg-no"
        
        await page.wait_for_selector(REG_NO_INPUT_SELECTOR, state='visible', timeout=30000)
        await page.fill(REG_NO_INPUT_SELECTOR, CAR_NUMBER)
        print(f">>> Registration Number filled: {CAR_NUMBER}")
        await asyncio.sleep(0.5) # Slight pause to simulate user input

        # ---------------- STEP 5: CLICK GET QUOTE ----------------
        print(">>> Clicking GET QUOTE")
        
        # Target the button using its unique ID
        QUOTE_BUTTON_SELECTOR = "a#_com_chola_insurance_products_web_InsuranceProductsPortlet_INSTANCE_ozvf_quote-btn"
        
        # Wait for the quote button to be visible/enabled
        await page.wait_for_selector(QUOTE_BUTTON_SELECTOR, state='visible', timeout=30000)

        # Click the button and wait for navigation to complete
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await page.click(QUOTE_BUTTON_SELECTOR)
        
        print(">>> Navigation to Quote Plan Page triggered.")
        
        # Final check
        print(">>> SUCCESS: Script execution complete. Currently at URL:")
        # print(await page.url)

        # Keep the browser open for 10 seconds for visual verification
        await asyncio.sleep(10)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())