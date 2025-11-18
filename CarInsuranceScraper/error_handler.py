"""
Comprehensive error handling utilities for GoDigit scraper
"""

import os
import sys
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any
import signal
from functools import wraps


class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, output_folder: str = "output"):
        """Initialize error handler"""
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True)
        self.log_file = self.output_folder / "error_log.txt"
        self._setup_logger()
        self.screenshot_folder = self.output_folder / "screenshots"
        self.screenshot_folder.mkdir(exist_ok=True)
        self._shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully"""
        self._shutdown_requested = True
        self.log_error("INTERRUPT", f"Received signal {signum}. Initiating graceful shutdown...")
        print("\n\n⚠️  Interrupt received. Cleaning up and shutting down gracefully...")
    
    def _setup_logger(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger("GoDigitScraper")
        self.logger.setLevel(logging.ERROR)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.ERROR)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_error(self, error_type: str, message: str, exception: Optional[Exception] = None):
        """Log error with full traceback"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_msg = f"[{timestamp}] [{error_type}] {message}"
        
        if exception:
            error_msg += f"\nException: {str(exception)}"
            error_msg += f"\nTraceback:\n{traceback.format_exc()}"
        
        self.logger.error(error_msg)
        return error_msg
    
    def capture_screenshot(self, page, error_type: str = "ERROR") -> Optional[str]:
        """Capture screenshot with timestamp"""
        try:
            if page is None:
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_{error_type}_{timestamp}.png"
            filepath = self.screenshot_folder / filename
            
            page.screenshot(path=str(filepath), full_page=True)
            self.log_error("SCREENSHOT", f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            self.log_error("SCREENSHOT_ERROR", f"Failed to capture screenshot: {str(e)}")
            return None
    
    def check_shutdown_requested(self) -> bool:
        """Check if shutdown was requested"""
        return self._shutdown_requested
    
    def handle_playwright_error(self, page, error: Exception, context: str = ""):
        """Handle Playwright-specific errors"""
        error_type = type(error).__name__
        message = f"Playwright error in {context}: {str(error)}"
        
        self.log_error("PLAYWRIGHT_ERROR", message, error)
        self.capture_screenshot(page, error_type)
        
        return {
            'error_type': error_type,
            'message': message,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
    
    def handle_network_error(self, page, error: Exception, context: str = ""):
        """Handle network-related errors"""
        error_type = type(error).__name__
        message = f"Network error in {context}: {str(error)}"
        
        self.log_error("NETWORK_ERROR", message, error)
        self.capture_screenshot(page, "NETWORK_ERROR")
        
        return {
            'error_type': error_type,
            'message': message,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
    
    def handle_scraping_error(self, page, error: Exception, partial_data: Optional[dict] = None):
        """Handle scraping errors with partial data"""
        error_type = type(error).__name__
        message = f"Scraping error: {str(error)}"
        
        self.log_error("SCRAPING_ERROR", message, error)
        self.capture_screenshot(page, "SCRAPING_ERROR")
        
        result = {
            'error_type': error_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'partial_data': partial_data
        }
        
        return result
    
    def handle_file_error(self, error: Exception, filepath: str, operation: str = "read"):
        """Handle file I/O errors"""
        error_type = type(error).__name__
        message = f"File {operation} error for {filepath}: {str(error)}"
        
        self.log_error("FILE_ERROR", message, error)
        
        return {
            'error_type': error_type,
            'message': message,
            'filepath': filepath,
            'operation': operation,
            'timestamp': datetime.now().isoformat()
        }


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"⚠️  Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")
                        print(f"   Retrying in {delay:.2f} seconds...")
                        import time
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        print(f"✗ All {max_retries + 1} attempts failed")
                        raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def safe_execute(func: Callable, error_handler: ErrorHandler, context: str = "", 
                 default_return=None, page=None):
    """
    Safely execute a function with error handling
    
    Args:
        func: Function to execute
        error_handler: ErrorHandler instance
        context: Context description for error messages
        default_return: Value to return on error
        page: Playwright page object for screenshots
    """
    try:
        return func()
    except Exception as e:
        error_handler.handle_playwright_error(page, e, context)
        if page:
            error_handler.capture_screenshot(page, "EXECUTION_ERROR")
        return default_return

