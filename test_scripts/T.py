# digit_full_pipeline.py

import json
import time
import random
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.godigit.com/"


CAR_NUMBER = "MH04KW1827"
MOBILE_NUMBER = " 8235268138"


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Opening homepage…")
        page.goto(BASE_URL, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        # -------------------------------------------------
        # 1) CLICK CAR OPTION (class="qf-switcher-img-holder")
        # -------------------------------------------------
        print("Selecting Car Insurance…")
        page.locator(".qf-switcher-img-holder").first.click()
        time.sleep(2)

        # -------------------------------------------------
        # 2) CLICK REGISTRATION NUMBER SECTION
        # (class="four-wheeler-form-label" id="title-car")
        # -------------------------------------------------
        print("Selecting Registration Number option…")
        page.locator('.four-wheeler-form-label#title-car').click()
        time.sleep(1)

        # -------------------------------------------------
        # 3) FILL CAR NUMBER
        # target div → class="searchfield-input input-field-wrapper mar__btm__none input-form-group has-error"
        # -------------------------------------------------
        print("Filling Registration Number…")

        reg_input = page.locator(
            'div.searchfield-input.input-field-wrapper.mar__btm__none.input-form-group.has-error input'
        )

        reg_input.wait_for(timeout=30000)
        reg_input.fill(CAR_NUMBER)
        print("Car No =", CAR_NUMBER)
        time.sleep(1)

        # -------------------------------------------------
        # 4) CLICK MOBILE NUMBER OPTION
        # (class="quote-option", id="car-mobile-number-option")
        # -------------------------------------------------
        print("Selecting mobile number field…")
        page.locator('.quote-option#car-mobile-number-option').click()
        time.sleep(1)

        # -------------------------------------------------
        # 5) FILL MOBILE NUMBER
        # input → id="car-mobile-number"
        # -------------------------------------------------
        print("Filling Mobile Number…")
        mobile_input = page.locator("#car-mobile-number")
        mobile_input.wait_for(timeout=10000)
        mobile_input.fill(MOBILE_NUMBER)
        print("Mobile =", MOBILE_NUMBER)
        time.sleep(1)

        # -------------------------------------------------
        # 6) CLICK “VIEW PRICE”
        # <div id="get-quote-div-reg"><button>View Prices</button>
        # -------------------------------------------------
        print("Clicking View Price…")
        view_btn = page.locator('#get-quote-div-reg button')
        view_btn.wait_for()
        view_btn.click(force=True)

        print("Waiting for plan page to load…")
        page.wait_for_load_state("networkidle")
        time.sleep(6)

        print("\n****************************************")
        print("✔ Navigation Successful — Plan Page Loaded")
        print("****************************************\n")

        # You can add scraping here later...

        browser.close()


if __name__ == "__main__":
    main()
