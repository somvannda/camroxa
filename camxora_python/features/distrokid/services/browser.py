"""
Browser Automation Module

Wrapper for Playwright browser automation with persistent sessions.
"""

from pathlib import Path
from typing import Optional, Callable
import logging
import time
import os

logger = logging.getLogger(__name__)

def _default_profile_dir() -> Path:
    try:
        from shared.lib.app_paths import get_user_data_dir

        return get_user_data_dir() / "distrokid" / "browser_profile"
    except Exception:  # noqa: BLE001
        return Path.home() / ".camxora" / "distrokid" / "browser_profile"


# Default profile directory for persistent sessions
DEFAULT_PROFILE_DIR = _default_profile_dir()


class BrowserError(Exception):
    """Exception raised when browser operations fail"""
    pass


class BrowserAutomation:
    """Playwright browser wrapper for web automation"""
    
    def __init__(self, headless: bool = False, profile_dir: Optional[Path] = None):
        """
        Initialize browser automation.
        
        Args:
            headless: Run browser in headless mode (default: False for visibility)
            profile_dir: Directory to persist browser profile (cookies, login state)
        """
        self.headless = headless
        self.profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._is_logged_in = False
        
        # Callbacks
        self._on_log: Optional[Callable] = None
    
    def set_callback(self, on_log: Optional[Callable] = None):
        """Set logging callback"""
        self._on_log = on_log
    
    def _log(self, message: str, level: str = "info"):
        """Log message"""
        getattr(logger, level)(message)
        if self._on_log:
            self._on_log(message)
    
    def launch(self):
        """Launch browser instance with persistent profile"""
        try:
            from playwright.sync_api import sync_playwright
            
            self._log("Launching browser...")
            self.playwright = sync_playwright().start()
            
            # Ensure profile directory exists
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            
            self._log(f"Using profile: {self.profile_dir}")
            
            # Try browsers in order: Playwright Chromium → System Chrome → Microsoft Edge
            channel = self._detect_browser_channel()
            
            launch_args = {
                'user_data_dir': str(self.profile_dir),
                'headless': self.headless,
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ],
                'ignore_default_args': ['--enable-automation']
            }
            
            if channel:
                launch_args['channel'] = channel
                self._log(f"Using browser: {channel}")
            else:
                self._log("Using Playwright bundled Chromium")
            
            self.context = self.playwright.chromium.launch_persistent_context(**launch_args)
            
            # Get or create page
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()
            
            # Mask webdriver detection
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            self._log("Browser launched with persistent session")
            
        except ImportError:
            raise BrowserError(
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install chromium"
            )
        except Exception as e:
            raise BrowserError(f"Failed to launch browser: {e}")
    
    def _detect_browser_channel(self):
        """Detect which browser to use.
        
        Priority:
        1. System Google Chrome → return "chrome"
        2. Microsoft Edge → return "msedge"
        3. Playwright Chromium (if installed with actual binaries) → return None
        """
        from pathlib import Path
        
        # Check for system Google Chrome first
        chrome_paths = [
            Path(os.environ.get("PROGRAMFILES", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for chrome_path in chrome_paths:
            if chrome_path.exists():
                return "chrome"
        
        # Fall back to Microsoft Edge (pre-installed on Windows 10/11)
        edge_paths = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
        for edge_path in edge_paths:
            if edge_path.exists():
                return "msedge"
        
        # Last resort: check for Playwright's bundled Chromium (with actual exe)
        home_browsers = Path.home() / "AppData" / "Local" / "ms-playwright"
        if home_browsers.exists():
            for item in home_browsers.iterdir():
                if item.name.startswith("chromium") and item.is_dir():
                    # Verify the chrome executable actually exists
                    chrome_exe = item / "chrome-win64" / "chrome.exe"
                    if chrome_exe.exists():
                        return None  # Use Playwright's Chromium
        
        # Nothing found — return None and let Playwright try its default
        return None

    def navigate(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 60000):
        """
        Navigate to URL.
        
        Args:
            url: URL to navigate to
            wait_until: Wait condition (load, domcontentloaded, networkidle)
            timeout: Navigation timeout in milliseconds (default: 60s)
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self._log(f"Navigating to: {url}")
        self.page.goto(url, wait_until=wait_until, timeout=timeout)
    
    def wait_for_selector(
        self,
        selector: str,
        timeout: int = 30000,
        state: str = "visible"
    ):
        """
        Wait for element to appear.
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
            state: Wait state (attached, detached, visible, hidden)
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout, state=state)
    
    def click(self, selector: str, timeout: int = 30000):
        """
        Click an element.
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.click(selector)
    
    def fill(self, selector: str, value: str, timeout: int = 30000):
        """
        Fill a form field.
        
        Args:
            selector: CSS selector
            value: Value to fill
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.fill(selector, value)
    
    def type_text(self, selector: str, text: str, delay: int = 50, timeout: int = 30000):
        """
        Type text character by character.
        
        Args:
            selector: CSS selector
            text: Text to type
            delay: Delay between characters in ms
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.type(selector, text, delay=delay)
    
    def select_option(self, selector: str, value: str, timeout: int = 30000):
        """
        Select an option from dropdown.
        
        Args:
            selector: CSS selector
            value: Option value
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.select_option(selector, value)
    
    def upload_file(self, selector: str, file_path: Path, timeout: int = 30000):
        """
        Upload file to file input.
        
        Args:
            selector: CSS selector for file input
            file_path: Path to file to upload
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        if not file_path.exists():
            raise BrowserError(f"File not found: {file_path}")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.set_input_files(selector, str(file_path))
    
    def upload_files(self, selector: str, file_paths: list[Path], timeout: int = 30000):
        """
        Upload multiple files to file input.
        
        Args:
            selector: CSS selector for file input
            file_paths: List of paths to files to upload
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        for file_path in file_paths:
            if not file_path.exists():
                raise BrowserError(f"File not found: {file_path}")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.set_input_files(selector, [str(p) for p in file_paths])
    
    def get_text(self, selector: str, timeout: int = 30000) -> str:
        """
        Get text content of element.
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
        
        Returns:
            Text content
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        return self.page.text_content(selector)
    
    def get_attribute(self, selector: str, attribute: str, timeout: int = 30000) -> str:
        """
        Get attribute value of element.
        
        Args:
            selector: CSS selector
            attribute: Attribute name
            timeout: Timeout in milliseconds
        
        Returns:
            Attribute value
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_selector(selector, timeout=timeout)
        return self.page.get_attribute(selector, attribute)
    
    def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        """
        Check if element is visible.
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
        
        Returns:
            True if visible, False otherwise
        """
        if not self.page:
            return False
        
        try:
            self.page.wait_for_selector(selector, timeout=timeout, state="visible")
            return True
        except Exception:
            return False
    
    def wait_for_load(self, timeout: int = 30000):
        """
        Wait for page to load.
        
        Args:
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
    
    def screenshot(self, path: Path):
        """
        Take screenshot.
        
        Args:
            path: Path to save screenshot
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        self.page.screenshot(path=str(path))
    
    def evaluate(self, expression: str):
        """
        Execute JavaScript expression.
        
        Args:
            expression: JavaScript expression to evaluate
        """
        if not self.page:
            raise BrowserError("Browser not launched")
        
        return self.page.evaluate(expression)
    
    def close(self):
        """Close browser - profile is saved automatically"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
            
            self._log("Browser closed - session saved")
            
        except Exception as e:
            self._log(f"Error closing browser: {e}", "warning")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
    
    def __enter__(self):
        """Context manager entry"""
        self.launch()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False


def create_browser(headless: bool = False) -> BrowserAutomation:
    """
    Create a browser automation instance.
    
    Args:
        headless: Run in headless mode
    
    Returns:
        BrowserAutomation instance
    """
    return BrowserAutomation(headless=headless)
