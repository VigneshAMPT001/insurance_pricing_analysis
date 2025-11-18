"""
Configuration file for GoDigit car insurance scraper
"""

# Car and user details
CAR_REGISTRATION = "MH04KW1827"
PHONE_NUMBER_PREFIX = "8"  # First digit of phone number

# GoDigit URLs
BASE_URL = "https://www.godigit.com/"
HOME_URL = "https://www.godigit.com/"
PLAN_PAGE_URL = "https://www.godigit.com/motor-insurance/car-flow/car-plan-page?session=KAIfDsEFGmSjSzadnjAUyuJ"

# Selectors for form filling
SELECTORS = {
    'car_button': 'text="Car"',  # First click - select car
    'registration_container': '#registration-container',
    'registration_input': '.searchfield-input.input-field-wrapper.mar__btm__none.input-form-group.has-success',
    'phone_container': '.input-container-box',
    'phone_prefix': '.pre-number.notranslate',
    'phone_input': 'input[type="tel"]',
    'view_price_button': '.text-sm.text-primary.carousel-cta',
    'km_range_radio': '.kmRangeRadio[value="0-4000 km (0-10 km/day)"]',
}

# Selectors for data scraping
DATA_SELECTORS = {
    'plan_container': '#plan-ComprehensiveWithPiCover',
    'claim_heading': '.claim-sub-heading.plr-8.br-1.mb-pl-0.ng-tns-c135-2',
    'claim_value': '.claim-value.notranslate.ng-tns-c135-2.ng-star-inserted',
    'claim_heading_2': '.claim-sub-heading.plr-8.ng-tns-c135-2.br-1',
    'claim_value_2': '.claim-value.notranslate.ng-tns-c135-2.ng-star-inserted',
    'checkbox_label': '.checkbox-label.d-flex.ng-tns-c135-326',
    'pa_owner_addon': '.paOwner-addon.ng-tns-c135-326.ng-star-inserted',
    'idv_container': '.ng-tns-c110-359',
    'idv_value': '.notranslate.ng-tns-c110-359',
    'total_premium_block': '.totalpremium-block.ng-star-inserted',
    'actual_premium': '#actualPremiumAmount.choose-plan-amount.notranslate.ng-star-inserted',
    'discounted_premium': '#premiumAmount.choose-plan-discounted-amount.notranslate.ng-star-inserted',
    'gst_text': '#gstTextMessage.choose-plan-gst-text.ng-star-inserted',
}

# Output settings
OUTPUT_FOLDER = 'output'
JSON_FILENAME = 'godigit_quotes.json'
CSV_FILENAME = 'godigit_quotes.csv'

# Browser settings
HEADLESS_MODE = False
TIMEOUT = 30000  # 30 seconds
SLOW_MO = 500  # Slow down by 500ms for visibility
