"""
Main execution script for GoDigit insurance scraper
Production-ready with comprehensive error handling
"""

import sys
import os
import signal
from pathlib import Path

# ✅ Ensure local imports work no matter where script is run from
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import configuration module; try normal import first, and fall back to loading config.py
# from the same directory to avoid unresolved-import issues when running as a script.
try:
    import config
except (ImportError, ModuleNotFoundError):
    import importlib.util
    config_path = os.path.join(script_dir, "config.py")
    if os.path.exists(config_path):
        try:
            spec = importlib.util.spec_from_file_location("config", config_path)
            config = importlib.util.module_from_spec(spec)
            if spec.loader:
                spec.loader.exec_module(config)
            else:
                raise ImportError(f"Failed to create loader for config module")
        except Exception as e:
            print(f"✗ Error loading config.py: {str(e)}")
            raise ImportError(f"Failed to load config from {config_path}: {str(e)}")
    else:
        raise ImportError(f"config.py not found at {config_path}. Please create it with required configuration.")
except Exception as e:
    print(f"✗ Unexpected error importing config: {str(e)}")
    raise

from godigit_scraper import GoDigitScraper
from data_handler import DataHandler
from error_handler import ErrorHandler


class ScraperApp:
    """Main application class with comprehensive error handling"""
    
    def __init__(self):
        """Initialize the scraper application"""
        self.error_handler = None
        self.data_handler = None
        self.scraper = None
        self._shutdown_requested = False
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self._shutdown_requested = True
            if self.error_handler:
                self.error_handler.log_error(
                    "SHUTDOWN_SIGNAL",
                    f"Received signal {signum}. Initiating graceful shutdown..."
                )
            print("\n\n⚠️  Interrupt received. Cleaning up and shutting down gracefully...")
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _print_progress(self, message: str, step: int = None, total: int = None):
        """Print progress message with optional step indicator"""
        if step is not None and total is not None:
            progress = f"[{step}/{total}]"
            print(f"{progress} {message}")
        else:
            print(message)
    
    def _check_shutdown(self) -> bool:
        """Check if shutdown was requested"""
        if self._shutdown_requested:
            return True
        if self.error_handler and self.error_handler.check_shutdown_requested():
            self._shutdown_requested = True
            return True
        return False
    
    def run(self):
        """Main execution function with comprehensive error handling"""
        print("="*70)
        print(" "*15 + "GODIGIT CAR INSURANCE SCRAPER")
        print("="*70)
        print("Production-ready with comprehensive error handling\n")
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Initialize error handler
        try:
            output_folder = getattr(config, 'OUTPUT_FOLDER', 'output')
            self.error_handler = ErrorHandler(output_folder)
            print("✓ Error handler initialized")
        except Exception as e:
            print(f"✗ Critical: Failed to initialize error handler: {str(e)}")
            return 1
        
        # Initialize data handler
        try:
            self._print_progress("Initializing data handler...", 1, 7)
            self.data_handler = DataHandler(
                getattr(config, 'OUTPUT_FOLDER', 'output'),
                getattr(config, 'JSON_FILENAME', 'godigit_quotes.json'),
                getattr(config, 'CSV_FILENAME', 'godigit_quotes.csv'),
                self.error_handler
            )
            print("✓ Data handler initialized")
        except Exception as e:
            self.error_handler.log_error("INIT_ERROR", f"Failed to initialize data handler: {str(e)}", e)
            print(f"✗ Failed to initialize data handler: {str(e)}")
            return 1
        
        # Initialize scraper configuration
        try:
            scraper_config = {
                'HOME_URL': getattr(config, 'HOME_URL', 'https://www.godigit.com/'),
                'BASE_URL': getattr(config, 'BASE_URL', 'https://www.godigit.com/'),
                'CAR_REGISTRATION': getattr(config, 'CAR_REGISTRATION', ''),
                'HEADLESS_MODE': getattr(config, 'HEADLESS_MODE', False),
                'TIMEOUT': getattr(config, 'TIMEOUT', 30000),
                'SLOW_MO': getattr(config, 'SLOW_MO', 500),
                'OUTPUT_FOLDER': getattr(config, 'OUTPUT_FOLDER', 'output')
            }
            
            self.scraper = GoDigitScraper(scraper_config, self.error_handler)
            print("✓ Scraper initialized")
        except Exception as e:
            self.error_handler.log_error("INIT_ERROR", f"Failed to initialize scraper: {str(e)}", e)
            print(f"✗ Failed to initialize scraper: {str(e)}")
            return 1
        
        # Main execution with guaranteed cleanup
        exit_code = 0
        scraped_data = None
        
        try:
            # Step 1: Setup browser
            if self._check_shutdown():
                print("⚠️  Shutdown requested before starting")
                return 0
            
            self._print_progress("Setting up browser...", 2, 7)
            if not self.scraper.setup_browser():
                print("✗ Failed to setup browser")
                self.error_handler.capture_screenshot(self.scraper.page, "BROWSER_SETUP_FAILED")
                return 1
            
            # Step 2: Navigate to home page
            if self._check_shutdown():
                print("⚠️  Shutdown requested")
                return 0
            
            self._print_progress("Navigating to home page...", 3, 7)
            if not self.scraper.navigate_to_home():
                print("✗ Failed to navigate to home page")
                self.error_handler.capture_screenshot(self.scraper.page, "NAVIGATION_FAILED")
                return 1
            
            # Step 3: Generate phone number
            if self._check_shutdown():
                print("⚠️  Shutdown requested")
                return 0
            
            self._print_progress("Generating phone number...", 4, 7)
            phone_number = self.scraper.generate_phone_number(
                getattr(config, 'PHONE_NUMBER_PREFIX', '8')
            )
            
            # Step 4: Fill form
            if self._check_shutdown():
                print("⚠️  Shutdown requested")
                return 0
            
            self._print_progress("Filling form...", 5, 7)
            print("\n" + "="*60)
            print("FILLING FORM")
            print("="*60)
            
            if not self.scraper.fill_form(
                getattr(config, 'CAR_REGISTRATION', ''),
                phone_number
            ):
                print("✗ Failed to fill form")
                self.error_handler.capture_screenshot(self.scraper.page, "FORM_FILL_FAILED")
                # Try to save any partial data
                return 1
            
            # Step 5: Scrape data
            if self._check_shutdown():
                print("⚠️  Shutdown requested, attempting to save partial data...")
                # Try to scrape whatever is available
                scraped_data = self.scraper.scrape_plan_details()
                if scraped_data:
                    is_partial = self._check_shutdown()
                    self.data_handler.save_to_json(scraped_data, partial=is_partial)
                return 0
            
            self._print_progress("Scraping plan details...", 6, 7)
            scraped_data = self.scraper.scrape_plan_details()
            
            if not scraped_data:
                print("✗ Failed to scrape data")
                self.error_handler.capture_screenshot(self.scraper.page, "SCRAPING_FAILED")
                return 1
            
            # Check if data is partial
            is_partial = bool(scraped_data.get('scraping_errors')) or self._check_shutdown()
            
            # Step 6: Save to JSON
            if self._check_shutdown():
                print("⚠️  Shutdown requested, saving partial data...")
            
            self._print_progress("Saving data to JSON...", 7, 7)
            if not self.data_handler.save_to_json(scraped_data, partial=is_partial):
                print("✗ Failed to save JSON (data may be lost)")
                self.error_handler.log_error("SAVE_ERROR", "Failed to save JSON data")
            else:
                if is_partial:
                    print("⚠️  Partial data saved to JSON")
                else:
                    print("✓ Data saved to JSON")
            
            # Step 7: Convert to CSV
            if not self._check_shutdown():
                print("\n📊 Converting to CSV...")
                csv_result = self.data_handler.load_and_convert()
                if csv_result is None:
                    print("⚠️  CSV conversion failed or skipped")
                else:
                    print("✓ CSV conversion completed")
            
            # Step 8: Display summary
            if not self._check_shutdown():
                print("\n📈 Generating summary...")
                summary = self.data_handler.display_summary()
                if summary is None:
                    print("⚠️  Summary generation failed or skipped")
            
            # Success message
            if not self._check_shutdown():
                print("\n" + "="*60)
                if is_partial:
                    print("⚠️  SCRAPING COMPLETED WITH WARNINGS")
                else:
                    print("✓ SCRAPING COMPLETED SUCCESSFULLY")
                print("="*60)
                output_folder = getattr(config, 'OUTPUT_FOLDER', 'output')
                json_filename = getattr(config, 'JSON_FILENAME', 'godigit_quotes.json')
                csv_filename = getattr(config, 'CSV_FILENAME', 'godigit_quotes.csv')
                print(f"JSON output: {output_folder}/{json_filename}")
                print(f"CSV output: {output_folder}/{csv_filename}")
                print(f"Error log: {output_folder}/error_log.txt")
                print(f"Screenshots: {output_folder}/screenshots/")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Script interrupted by user (KeyboardInterrupt)")
            self.error_handler.log_error("KEYBOARD_INTERRUPT", "User interrupted the script")
            exit_code = 130  # Standard exit code for SIGINT
        except Exception as e:
            print(f"\n✗ Unexpected error: {str(e)}")
            self.error_handler.log_error("UNEXPECTED_ERROR", f"Unexpected error in main execution: {str(e)}", e)
            if self.scraper and self.scraper.page:
                self.error_handler.capture_screenshot(self.scraper.page, "UNEXPECTED_ERROR")
            
            # Try to save partial data if available
            if scraped_data:
                try:
                    print("💾 Attempting to save partial data...")
                    self.data_handler.save_to_json(scraped_data, partial=True)
                    print("✓ Partial data saved")
                except Exception as save_error:
                    self.error_handler.log_error("PARTIAL_SAVE_ERROR", f"Failed to save partial data: {str(save_error)}", save_error)
            
            exit_code = 1
        finally:
            # GUARANTEED CLEANUP - This block always executes
            print("\n" + "="*60)
            print("CLEANUP")
            print("="*60)
            
            try:
                if self.scraper:
                    print("🔄 Closing browser...")
                    self.scraper.close()
                    print("✓ Cleanup completed")
                else:
                    print("⚠️  No scraper instance to clean up")
            except Exception as cleanup_error:
                self.error_handler.log_error(
                    "CLEANUP_ERROR",
                    f"Error during cleanup: {str(cleanup_error)}",
                    cleanup_error
                )
                print(f"⚠️  Cleanup error: {str(cleanup_error)}")
            
            # Final status
            if exit_code == 0:
                print("\n✓ Application exited successfully")
            else:
                print(f"\n⚠️  Application exited with code {exit_code}")
                print(f"Check error log: {getattr(config, 'OUTPUT_FOLDER', 'output')}/error_log.txt")
        
        return exit_code


def main():
    """Entry point"""
    app = ScraperApp()
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
