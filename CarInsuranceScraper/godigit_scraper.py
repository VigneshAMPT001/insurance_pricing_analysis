"""
GoDigit insurance scraper using Playwright and BeautifulSoup
Production-ready with comprehensive error handling
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError
from bs4 import BeautifulSoup
import time
import random
import re
import subprocess
from typing import Optional, List, Dict, Any
from error_handler import ErrorHandler, retry_with_backoff, safe_execute


class GoDigitScraper:
    def __init__(self, config, error_handler: Optional[ErrorHandler] = None):
        """Initialize scraper with configuration"""
        self.config = config
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.error_handler = error_handler or ErrorHandler(config.get('OUTPUT_FOLDER', 'output'))
        self._browser_initialized = False
        
    def setup_browser(self):
        """Setup Playwright browser with retry logic"""
        @retry_with_backoff(max_retries=3, initial_delay=2.0, 
                           exceptions=(PlaywrightError, Exception))
        def _setup():
            try:
                print("🔄 Initializing browser...")
                self.playwright = sync_playwright().start()
                
                browser_options = {
                    'headless': self.config.get('HEADLESS_MODE', False),
                    'slow_mo': self.config.get('SLOW_MO', 500)
                }
                
                self.browser = self.playwright.chromium.launch(**browser_options)

                # Use a browser context to set a realistic user agent and consistent viewport
                context_options = {
                    "user_agent": self.config.get(
                        'USER_AGENT',
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                    ),
                    "viewport": {"width": 1920, "height": 1080},
                    "locale": "en-US"
                }
                self.context = self.browser.new_context(**context_options)
                self.page = self.context.new_page()
                self.page.set_default_timeout(self.config.get('TIMEOUT', 30000))
                
                # Set viewport for consistent rendering
                self.page.set_viewport_size({"width": 1920, "height": 1080})
                
                self._browser_initialized = True
                print("✓ Browser initialized successfully")
                return True
            except PlaywrightError as e:
                self.error_handler.handle_playwright_error(self.page, e, "Browser setup")
                raise
            except Exception as e:
                self.error_handler.log_error("BROWSER_SETUP", f"Unexpected error: {str(e)}", e)
                raise
        
        try:
            return _setup()
        except Exception as e:
            print(f"✗ Failed to setup browser after retries: {str(e)}")
            return False
    
    def generate_phone_number(self, prefix="8"):
        """Generate random 10-digit phone number starting with given prefix"""
        try:
            remaining_digits = ''.join([str(random.randint(0, 9)) for _ in range(9)])
            phone = prefix + remaining_digits
            print(f"✓ Generated phone number: {phone}")
            return phone
        except Exception as e:
            self.error_handler.log_error("PHONE_GENERATION", f"Error generating phone: {str(e)}", e)
            # Fallback phone number
            return prefix + "000000000"
    
    def _find_element_with_fallbacks(self, selectors: List[str], operation: str = "click", 
                                     value: Optional[str] = None, timeout: int = 10000) -> bool:
        """
        Try multiple selectors with fallback strategy
        
        Args:
            selectors: List of selector strings to try
            operation: Operation to perform ('click', 'fill', 'wait')
            value: Value to fill (for 'fill' operation)
            timeout: Timeout per selector attempt
        """
        if not self.page:
            return False
        
        last_error = None
        for idx, selector in enumerate(selectors):
            try:
                if operation == "click":
                    self.page.click(selector, timeout=timeout)
                    return True
                elif operation == "fill":
                    self.page.fill(selector, value, timeout=timeout)
                    return True
                elif operation == "wait":
                    self.page.wait_for_selector(selector, timeout=timeout)
                    return True
            except (PlaywrightTimeout, PlaywrightError) as e:
                last_error = e
                if idx < len(selectors) - 1:
                    print(f"  ⚠️  Selector {idx + 1} failed, trying next...")
                    continue
                else:
                    self.error_handler.handle_playwright_error(
                        self.page, e, f"Element not found with all selectors: {selectors}"
                    )
        
        if last_error:
            self.error_handler.capture_screenshot(self.page, "ELEMENT_NOT_FOUND")
        return False
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0, 
                       exceptions=(PlaywrightTimeout, PlaywrightError))
    def navigate_to_home(self):
        """Navigate to GoDigit home page with retry logic"""
        try:
            if self.error_handler.check_shutdown_requested():
                print("⚠️  Shutdown requested, aborting navigation")
                return False
            
            url = self.config['HOME_URL']
            print(f"🔄 Navigating to: {url}")
            
            # Navigate with network error handling
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if response and response.status >= 400:
                raise PlaywrightError(f"HTTP {response.status} error loading {url}")
            
            # Wait for page to be ready
            self.page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)  # Additional wait for dynamic content
            
            print("✓ Reached home page successfully")
            return True
            
        except PlaywrightTimeout as e:
            self.error_handler.handle_network_error(self.page, e, "Navigation timeout")
            raise
        except PlaywrightError as e:
            self.error_handler.handle_network_error(self.page, e, "Navigation error")
            raise
        except Exception as e:
            self.error_handler.handle_network_error(self.page, e, "Unexpected navigation error")
            raise
    
    def fill_form(self, car_number, phone_number):
        """Fill the insurance form step by step with comprehensive error handling"""
        partial_data = {'step': 0, 'car_number': car_number, 'phone_number': phone_number}
        
        try:
            if self.error_handler.check_shutdown_requested():
                print("⚠️  Shutdown requested, aborting form fill")
                return False
            
            # Step 1: Click on Car button
            print("\n📝 Step 1: Clicking on Car...")
            partial_data['step'] = 1
            car_selectors = [
                'text="Car"',
                'button:has-text("Car")',
                '[data-testid="car-button"]',
                '.car-button',
                '//button[contains(text(), "Car")]'
            ]
            
            if not self._find_element_with_fallbacks(car_selectors, "click", timeout=15000):
                print("✗ Failed to click Car button")
                return False
            
            time.sleep(2)
            print("✓ Car selected")
            
            # Step 2: Fill car registration number
            print(f"📝 Step 2: Filling car registration: {car_number}")
            partial_data['step'] = 2
            registration_selectors = [
                '#registration-container input',
                '.searchfield-input.input-field-wrapper input',
                'input[placeholder*="registration" i]',
                'input[placeholder*="number" i]',
                '.input-field-wrapper input'
            ]
            
            if not self._find_element_with_fallbacks(registration_selectors, "fill", 
                                                    value=car_number, timeout=15000):
                print("✗ Failed to fill car registration")
                return False
            
            time.sleep(1)
            print("✓ Car registration filled")
            
            # Step 3: Click to proceed (if needed)
            print("📝 Step 3: Proceeding to next step...")
            partial_data['step'] = 3
            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                '.continue-button',
                '[data-testid="continue-button"]',
                '//button[contains(text(), "Continue")]'
            ]
            
            # This step is optional, so we don't fail if it doesn't exist
            self._find_element_with_fallbacks(continue_selectors, "click", timeout=5000)
            time.sleep(2)
            
            # Step 4: Fill phone number
            print(f"📝 Step 4: Filling phone number: {phone_number}")
            partial_data['step'] = 4
            phone_selectors = [
                'input[type="tel"]',
                '.input-container-box input',
                'input[placeholder*="phone" i]',
                'input[placeholder*="mobile" i]',
                '#phone-input'
            ]
            
            if not self._find_element_with_fallbacks(phone_selectors, "fill", 
                                                    value=phone_number, timeout=15000):
                print("✗ Failed to fill phone number")
                return False
            
            time.sleep(1)
            print("✓ Phone number filled")
            
            # Step 5: Agree to Terms & Conditions if present
            print("📝 Step 5: Agreeing to Terms & Conditions if required...")
            partial_data['step'] = 5
            terms_selectors = [
                'input[type="checkbox"]',
                'label:has-text("I agree to the Terms")',
                'text="I agree to the Terms & Conditions"',
                '[for*="terms"]',
                '[name*="terms"]'
            ]
            # Optional – do not fail if absent
            try:
                agreed = self._find_element_with_fallbacks(terms_selectors, "click", timeout=4000)
                if agreed:
                    print("✓ Terms & Conditions accepted")
            except Exception:
                pass

            # Step 6: Click View Price
            print("📝 Step 6: Clicking View Price...")
            partial_data['step'] = 6
            view_price_selectors = [
                '.text-sm.text-primary.carousel-cta',
                'button:has-text("View Prices")',
                'button:has-text("View Price")',
                'button:has-text("Get Quote")',
                '[data-testid="view-price"]',
                '//button[contains(text(), "View Price")]',
                '//button[contains(text(), "View Prices")]'
            ]
            
            if not self._find_element_with_fallbacks(view_price_selectors, "click", timeout=15000):
                print("✗ Failed to click View Price")
                return False
            
            time.sleep(3)
            print("✓ View Price clicked")
            
            # Step 7: Select KM range (if shown)
            print("📝 Step 7: Selecting KM range if visible...")
            partial_data['step'] = 7
            km_selectors = [
                'input[value="0-4000 km (0-10 km/day)"]',
                '.kmRangeRadio >> nth=0',
                'input[type="radio"][value*="0-4000"]',
                '.km-range-radio:first-of-type',
                '//input[@type="radio" and contains(@value, "0-4000")]'
            ]
            
            if not self._find_element_with_fallbacks(km_selectors, "click", timeout=15000):
                print("⚠️  KM range selection failed, but continuing...")
            else:
                time.sleep(2)
                print("✓ KM range selected")
            
            # Wait for plan page to load with multiple selector strategies
            print("📝 Waiting for plan page to load...")
            plan_container_selectors = [
                '#plan-ComprehensiveWithPiCover',
                '[id*="plan"]',
                '.plan-container',
                '.insurance-plan',
                '[class*="plan"]'
            ]
            
            plan_loaded = False
            for selector in plan_container_selectors:
                try:
                    self.page.wait_for_selector(selector, timeout=20000)
                    plan_loaded = True
                    break
                except PlaywrightTimeout:
                    continue
            
            if not plan_loaded:
                print("⚠️  Plan container not found with standard selectors, checking page state...")
                self.error_handler.capture_screenshot(self.page, "PLAN_PAGE_NOT_LOADED")
                # Don't fail completely, try to continue
                time.sleep(5)  # Give more time for dynamic loading
            
            print("✓ Plan page loaded successfully")
            return True
            
        except PlaywrightTimeout as e:
            self.error_handler.handle_playwright_error(self.page, e, f"Form fill timeout at step {partial_data['step']}")
            self.error_handler.capture_screenshot(self.page, "FORM_FILL_TIMEOUT")
            return False
        except PlaywrightError as e:
            self.error_handler.handle_playwright_error(self.page, e, f"Form fill error at step {partial_data['step']}")
            self.error_handler.capture_screenshot(self.page, "FORM_FILL_ERROR")
            return False
        except Exception as e:
            self.error_handler.handle_playwright_error(self.page, e, f"Unexpected form fill error at step {partial_data['step']}")
            self.error_handler.capture_screenshot(self.page, "FORM_FILL_UNEXPECTED")
            return False
    
    def scrape_plan_details(self):
        """Scrape all plan details using BeautifulSoup with partial data saving"""
        partial_data = {
            'variants': [],
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'car_number': self.config.get('CAR_REGISTRATION', ''),
            'page_url': self.page.url if self.page else '',
            'scraping_errors': []
        }
        
        try:
            if self.error_handler.check_shutdown_requested():
                print("⚠️  Shutdown requested, saving partial data...")
                return partial_data if partial_data['variants'] else None
            
            print("\n" + "="*60)
            print("SCRAPING PLAN DETAILS")
            print("="*60)
            
            # Get page HTML with error handling
            try:
                html_content = self.page.content()
            except Exception as e:
                self.error_handler.handle_scraping_error(self.page, e, partial_data)
                return partial_data if partial_data['variants'] else None
            
            # Parse with BeautifulSoup
            try:
                soup = BeautifulSoup(html_content, 'lxml')
            except Exception as e:
                self.error_handler.log_error("PARSING_ERROR", f"Failed to parse HTML: {str(e)}", e)
                # Try with html.parser as fallback
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                except Exception as e2:
                    self.error_handler.handle_scraping_error(self.page, e2, partial_data)
                    return partial_data if partial_data['variants'] else None
            
            # Find plan container with multiple strategies
            plan_container = None
            container_selectors = [
                {'id': 'plan-ComprehensiveWithPiCover'},
                {'class': re.compile('plan-container')},
                {'class': re.compile('insurance-plan')},
                {'id': re.compile('plan')},
                {'class': re.compile('.*plan.*', re.I)}
            ]
            
            for selector in container_selectors:
                try:
                    if 'id' in selector:
                        plan_container = soup.find(id=selector['id'])
                    elif 'class' in selector:
                        plan_container = soup.find(class_=selector['class'])
                    
                    if plan_container:
                        break
                except Exception as e:
                    continue
            
            if not plan_container:
                error_msg = "Plan container not found with any selector strategy"
                self.error_handler.log_error("SCRAPING_ERROR", error_msg)
                self.error_handler.capture_screenshot(self.page, "PLAN_CONTAINER_NOT_FOUND")
                partial_data['scraping_errors'].append(error_msg)
                # Try to extract whatever we can
                plan_container = soup
            
            # Extract all variants (if multiple plans exist)
            variant_sections = []
            variant_strategies = [
                soup.find_all(class_=re.compile('plan-card|insurance-plan')),
                soup.find_all(id=re.compile('plan')),
                soup.find_all('div', class_=re.compile('.*plan.*', re.I)),
                [plan_container] if plan_container else []
            ]
            
            for strategy in variant_strategies:
                if strategy:
                    variant_sections = strategy
                    break
            
            if not variant_sections:
                variant_sections = [plan_container] if plan_container else []
            
            print(f"📊 Found {len(variant_sections)} variant(s) to extract")
            
            for idx, variant in enumerate(variant_sections):
                if self.error_handler.check_shutdown_requested():
                    print(f"⚠️  Shutdown requested after variant {idx}")
                    break
                
                print(f"\n📦 Extracting Variant {idx + 1}...")
                
                variant_data = {
                    'variant_number': idx + 1,
                    'insurer': 'GoDigit',
                }
                
                # Extract Claim details with error handling
                try:
                    claim_headings = variant.find_all(class_=re.compile('claim-sub-heading|claim.*heading', re.I))
                    claim_values = variant.find_all(class_=re.compile('claim-value|claim.*value', re.I))
                    
                    # Fallback strategies for claims
                    if not claim_headings:
                        claim_headings = variant.find_all(string=re.compile('claim', re.I))
                    if not claim_values:
                        claim_values = variant.find_all(class_=re.compile('value|amount', re.I))
                    
                    claims = {}
                    for heading, value in zip(claim_headings, claim_values):
                        try:
                            claim_type = heading.get_text(strip=True) if hasattr(heading, 'get_text') else str(heading).strip()
                            claim_amount = value.get_text(strip=True) if hasattr(value, 'get_text') else str(value).strip()
                            if claim_type and claim_amount:
                                claims[claim_type] = claim_amount
                        except Exception:
                            continue
                    
                    variant_data['claims'] = claims
                    print(f"  ✓ Claims extracted: {len(claims)} items")
                except Exception as e:
                    error_msg = f"Claims extraction failed: {str(e)}"
                    partial_data['scraping_errors'].append(error_msg)
                    print(f"  ⚠️  {error_msg}")
                    variant_data['claims'] = {}
                
                # Extract IDV (Insured Declared Value) with multiple strategies
                try:
                    idv_strategies = [
                        variant.find(class_=re.compile('notranslate.*tns-c110')),
                        variant.find(class_='notranslate.ng-tns-c110-359'),
                        variant.find(string=re.compile('IDV|Insured.*Value', re.I)),
                        variant.find(id=re.compile('idv', re.I)),
                        variant.find(class_=re.compile('idv|insured.*value', re.I))
                    ]
                    
                    idv_element = None
                    for strategy in idv_strategies:
                        if strategy:
                            idv_element = strategy
                            break
                    
                    if idv_element:
                        if hasattr(idv_element, 'get_text'):
                            idv_value = idv_element.get_text(strip=True)
                        else:
                            idv_value = str(idv_element).strip()
                        variant_data['idv'] = idv_value
                        print(f"  ✓ IDV: {idv_value}")
                    else:
                        variant_data['idv'] = None
                except Exception as e:
                    error_msg = f"IDV extraction failed: {str(e)}"
                    partial_data['scraping_errors'].append(error_msg)
                    print(f"  ⚠️  {error_msg}")
                    variant_data['idv'] = None
                
                # Extract Premium details with multiple strategies
                try:
                    # Actual Premium
                    actual_premium_strategies = [
                        variant.find(id='actualPremiumAmount'),
                        variant.find(class_='choose-plan-amount'),
                        variant.find(string=re.compile('actual.*premium', re.I)),
                        variant.find(class_=re.compile('actual.*premium|premium.*amount', re.I))
                    ]
                    
                    actual_premium_elem = None
                    for strategy in actual_premium_strategies:
                        if strategy:
                            actual_premium_elem = strategy
                            break
                    
                    if actual_premium_elem:
                        variant_data['actual_premium'] = actual_premium_elem.get_text(strip=True) if hasattr(actual_premium_elem, 'get_text') else str(actual_premium_elem).strip()
                        print(f"  ✓ Actual Premium: {variant_data['actual_premium']}")
                    
                    # Discounted Premium
                    discounted_premium_strategies = [
                        variant.find(id='premiumAmount'),
                        variant.find(class_='choose-plan-discounted-amount'),
                        variant.find(string=re.compile('discounted.*premium', re.I)),
                        variant.find(class_=re.compile('discounted.*premium', re.I))
                    ]
                    
                    discounted_premium_elem = None
                    for strategy in discounted_premium_strategies:
                        if strategy:
                            discounted_premium_elem = strategy
                            break
                    
                    if discounted_premium_elem:
                        variant_data['discounted_premium'] = discounted_premium_elem.get_text(strip=True) if hasattr(discounted_premium_elem, 'get_text') else str(discounted_premium_elem).strip()
                        print(f"  ✓ Discounted Premium: {variant_data['discounted_premium']}")
                    
                    # GST text
                    gst_strategies = [
                        variant.find(id='gstTextMessage'),
                        variant.find(class_='choose-plan-gst-text'),
                        variant.find(string=re.compile('GST', re.I)),
                        variant.find(class_=re.compile('gst', re.I))
                    ]
                    
                    gst_elem = None
                    for strategy in gst_strategies:
                        if strategy:
                            gst_elem = strategy
                            break
                    
                    if gst_elem:
                        variant_data['gst_info'] = gst_elem.get_text(strip=True) if hasattr(gst_elem, 'get_text') else str(gst_elem).strip()
                        print(f"  ✓ GST Info: {variant_data['gst_info']}")
                    
                except Exception as e:
                    error_msg = f"Premium extraction partial: {str(e)}"
                    partial_data['scraping_errors'].append(error_msg)
                    print(f"  ⚠️  {error_msg}")
                
                # Extract Add-ons (PA Owner, etc.)
                try:
                    addons = []
                    addon_strategies = [
                        variant.find_all(class_=re.compile('paOwner-addon|checkbox-label')),
                        variant.find_all(string=re.compile('add.*on|PA.*Owner', re.I)),
                        variant.find_all(class_=re.compile('addon|checkbox', re.I))
                    ]
                    
                    addon_elements = []
                    for strategy in addon_strategies:
                        if strategy:
                            addon_elements = strategy
                            break
                    
                    for addon in addon_elements:
                        try:
                            addon_text = addon.get_text(strip=True) if hasattr(addon, 'get_text') else str(addon).strip()
                            if addon_text:
                                addons.append(addon_text)
                        except Exception:
                            continue
                    
                    variant_data['addons'] = addons
                    print(f"  ✓ Add-ons: {len(addons)} items")
                except Exception as e:
                    error_msg = f"Add-ons extraction failed: {str(e)}"
                    partial_data['scraping_errors'].append(error_msg)
                    print(f"  ⚠️  {error_msg}")
                    variant_data['addons'] = []
                
                # Extract NCB if available
                try:
                    ncb_strategies = [
                        variant.find(string=re.compile('NCB|No Claim Bonus', re.IGNORECASE)),
                        variant.find(class_=re.compile('ncb|no.*claim', re.I)),
                        variant.find(id=re.compile('ncb', re.I))
                    ]
                    
                    ncb_element = None
                    for strategy in ncb_strategies:
                        if strategy:
                            ncb_element = strategy
                            break
                    
                    if ncb_element:
                        if hasattr(ncb_element, 'find_parent'):
                            ncb_parent = ncb_element.find_parent()
                            ncb_value = ncb_parent.find_next_sibling() if ncb_parent else None
                            if ncb_value:
                                variant_data['ncb'] = ncb_value.get_text(strip=True) if hasattr(ncb_value, 'get_text') else str(ncb_value).strip()
                            else:
                                variant_data['ncb'] = "0%"
                        else:
                            variant_data['ncb'] = str(ncb_element).strip()
                    else:
                        variant_data['ncb'] = "0%"
                except Exception as e:
                    variant_data['ncb'] = "0%"
                
                partial_data['variants'].append(variant_data)
            
            if partial_data['scraping_errors']:
                print(f"\n⚠️  Completed with {len(partial_data['scraping_errors'])} error(s)")
            else:
                print(f"\n✓ Successfully scraped {len(partial_data['variants'])} variant(s)")
            
            return partial_data
            
        except PlaywrightTimeout as e:
            self.error_handler.handle_scraping_error(self.page, e, partial_data)
            return partial_data if partial_data['variants'] else None
        except PlaywrightError as e:
            self.error_handler.handle_scraping_error(self.page, e, partial_data)
            return partial_data if partial_data['variants'] else None
        except Exception as e:
            self.error_handler.handle_scraping_error(self.page, e, partial_data)
            return partial_data if partial_data['variants'] else None
    
    def close(self):
        """Close browser and cleanup with guaranteed execution"""
        cleanup_errors = []
        
        try:
            if self.context:
                try:
                    for page in self.context.pages:
                        try:
                            page.close()
                        except Exception as e:
                            cleanup_errors.append(f"Error closing page: {str(e)}")
                    self.context.close()
                    print("✓ Context closed")
                except Exception as e:
                    cleanup_errors.append(f"Error closing context: {str(e)}")
                    self.error_handler.log_error("CONTEXT_CLEANUP", f"Context close error: {str(e)}", e)

            if self.browser:
                try:
                    # Close browser
                    self.browser.close()
                    print("✓ Browser closed")
                except Exception as e:
                    cleanup_errors.append(f"Error closing browser: {str(e)}")
                    self.error_handler.log_error("BROWSER_CLEANUP", f"Browser close error: {str(e)}", e)
            
            if self.playwright:
                try:
                    self.playwright.stop()
                    print("✓ Playwright stopped")
                except Exception as e:
                    cleanup_errors.append(f"Error stopping playwright: {str(e)}")
                    self.error_handler.log_error("PLAYWRIGHT_CLEANUP", f"Playwright stop error: {str(e)}", e)
            
            self._browser_initialized = False
            
            if cleanup_errors:
                print(f"⚠️  Cleanup completed with {len(cleanup_errors)} warning(s)")
                for error in cleanup_errors:
                    print(f"   - {error}")
        except Exception as e:
            self.error_handler.log_error("CLEANUP_ERROR", f"Unexpected cleanup error: {str(e)}", e)
            print(f"⚠️  Error during cleanup: {str(e)}")
        finally:
            # Force cleanup if still initialized
            if self._browser_initialized:
                try:
                    # Kill any remaining browser processes (last resort)
                    subprocess.run(['pkill', '-f', 'chromium'], stderr=subprocess.DEVNULL, timeout=5)
                except Exception:
                    pass
