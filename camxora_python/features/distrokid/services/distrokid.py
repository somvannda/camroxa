"""
DistroKid Automation Module

Handles DistroKid-specific browser automation for uploading music.
"""

from pathlib import Path
from typing import Optional, Callable
import logging
import time

from features.distrokid.services.browser import BrowserAutomation, BrowserError

logger = logging.getLogger(__name__)


class DistroKidError(Exception):
    """Exception raised when DistroKid operations fail"""
    pass


class DistroKidLoginError(DistroKidError):
    """Exception raised when login fails"""
    pass


class DistroKidUploadError(DistroKidError):
    """Exception raised when upload fails"""
    pass


# DistroKid URLs
DISTROKID_BASE_URL = "https://distrokid.com"
DISTROKID_LOGIN_URL = f"{DISTROKID_BASE_URL}/login"
DISTROKID_DASHBOARD_URL = f"{DISTROKID_BASE_URL}/mymusic"
DISTROKID_UPLOAD_URL = f"{DISTROKID_BASE_URL}/new/"

# CSS Selectors (may need updates as DistroKid changes their UI)
SELECTORS = {
    # Login page
    "login_email": "input[name='email']",
    "login_password": "input[name='password']",
    "login_button": "button[type='submit']",
    "login_error": ".error-message, .alert-danger",
    
    # Dashboard
    "upload_button": "a[href*='upload'], button:has-text('Upload')",
    "profile_menu": ".profile-menu, [data-testid='profile-menu']",
    
    # Upload page
    "album_title": "input[name='albumTitle'], #albumTitle",
    "artist_name": "input[name='artistName'], #artistName",
    "genre_select": "select[name='genre'], #genre, #genrePrimary",
    "subgenre_select": "select[name='subgenre'], #subgenre",
    "release_date": "input[name='releaseDate'], #releaseDate",
    "track_upload": "input[type='file'][accept*='audio']",
    "track_title": "input[name*='trackTitle'], input[placeholder*='Track']",
    "artwork_upload": "input[type='file'][accept*='image']",
    "submit_button": "button[type='submit']:has-text('Submit'), button:has-text('Upload')",
    
    # Confirmation/Success
    "success_message": ".success-message, .alert-success",
    "error_message": ".error-message, .alert-danger",
}


class DistroKidAutomation:
    """DistroKid-specific browser automation"""
    
    def __init__(self, browser: BrowserAutomation):
        """
        Initialize DistroKid automation.
        
        Args:
            browser: BrowserAutomation instance
        """
        self.browser = browser
        self._is_logged_in = False
        
        # Callbacks
        self._on_log: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_log: Optional[Callable] = None,
        on_progress: Optional[Callable] = None
    ):
        """Set callback functions"""
        self._on_log = on_log
        self._on_progress = on_progress
        self.browser.set_callback(on_log)
    
    def _log(self, message: str, level: str = "info"):
        """Log message"""
        getattr(logger, level)(message)
        if self._on_log:
            self._on_log(message)
    
    def _update_progress(self, current: int, total: int, message: str):
        """Update progress"""
        if self._on_progress:
            self._on_progress(current, total, message)
    
    def login(self, email: str = "", password: str = "") -> bool:
        """
        Login to DistroKid using Google Sign-In.
        
        If already logged in from a previous session, will reuse the saved session.
        For first-time login, user must complete Google Sign-In and 2FA manually.
        
        Args:
            email: Not used for Google Sign-In (kept for compatibility)
            password: Not used for Google Sign-In (kept for compatibility)
        
        Returns:
            True if login successful
        
        Raises:
            DistroKidLoginError: If login fails
        """
        try:
            self._log("Checking DistroKid login status...")
            
            # Navigate to DistroKid
            self.browser.navigate(DISTROKID_BASE_URL)
            time.sleep(3)
            
            current_url = self.browser.page.url
            self._log(f"Landed on: {current_url}")
            
            # Check if already logged in (persistent session)
            if self._check_login_success():
                self._is_logged_in = True
                self._log("✓ Already logged in (session restored)")
                return True
            
            # Try navigating directly to the upload page - if it works, we're logged in
            self._log("Checking if we can access upload page directly...")
            self.browser.navigate(DISTROKID_UPLOAD_URL)
            time.sleep(3)
            
            current_url = self.browser.page.url
            self._log(f"Upload page URL: {current_url}")
            
            # If we weren't redirected to login, we're authenticated
            if "login" not in current_url.lower() and "signin" not in current_url.lower():
                self._is_logged_in = True
                self._log("✓ Logged in - can access upload page")
                return True
            
            self._log("Not logged in - please complete Google Sign-In manually")
            self._log("1. Click 'Sign in with Google'")
            self._log("2. Complete Google login and 2FA")
            self._log("3. Wait for dashboard to load")
            
            # Navigate to login page
            self.browser.navigate(DISTROKID_LOGIN_URL)
            time.sleep(2)
            
            # Try to find and click Google Sign-In button
            google_selectors = [
                "button:has-text('Google')",
                "a:has-text('Google')",
                "[data-provider='google']",
                ".google-login",
                "#google-signin",
                "button:has-text('Sign in with Google')",
            ]
            
            clicked_google = False
            for selector in google_selectors:
                try:
                    if self.browser.is_visible(selector, timeout=3000):
                        self.browser.click(selector)
                        clicked_google = True
                        self._log("Clicked Google Sign-In button")
                        break
                except:
                    continue
            
            if not clicked_google:
                self._log("Please click 'Sign in with Google' manually")
            
            # Wait for user to complete login and 2FA
            self._log("⏳ Waiting for you to complete login (up to 10 minutes)...")
            self._log("Please sign in with Google in the browser window.")
            self._log("(Session will be saved — you won't need to login again)")
            
            # Wait up to 10 minutes for login to complete
            max_wait = 600  # 10 minutes
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(5)  # Check every 5 seconds (gives user time)
                
                current_url = self.browser.page.url
                
                # Check if we left the login/signin page
                if "login" not in current_url.lower() and "signin" not in current_url.lower() and "accounts.google" not in current_url.lower():
                    self._is_logged_in = True
                    self._log(f"✓ Login successful! Now at: {current_url}")
                    return True
                
                if self._check_login_success():
                    self._is_logged_in = True
                    self._log("✓ Login successful! Session saved.")
                    return True
            
            raise DistroKidLoginError("Login timed out after 5 minutes. Please try again.")
            
        except BrowserError as e:
            raise DistroKidLoginError(f"Login failed: {e}")
        except Exception as e:
            if isinstance(e, DistroKidLoginError):
                raise
            raise DistroKidLoginError(f"Login failed: {e}")
    
    def _check_login_success(self) -> bool:
        """Check if login was successful by examining the current page"""
        try:
            current_url = self.browser.page.url
            
            # If we're on any DistroKid page that isn't login, we're probably logged in
            if "distrokid.com" in current_url:
                # These pages mean we're NOT logged in
                if "login" in current_url or "signin" in current_url:
                    return False
                # These pages mean we ARE logged in
                if any(x in current_url for x in ["dashboard", "upload", "mymusic", "bank", "stats", "profile", "settings"]):
                    return True
            
            # Check for profile menu or any logged-in indicator
            logged_in_selectors = [
                SELECTORS["profile_menu"],
                "a[href*='mymusic']",
                "a[href*='dashboard']",
                "a[href*='upload']",
                "[class*='avatar']",
                "[class*='user']",
                "a[href*='logout']",
                "a[href*='signout']",
            ]
            
            for selector in logged_in_selectors:
                try:
                    if self.browser.is_visible(selector, timeout=2000):
                        return True
                except:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def _get_error_message(self) -> Optional[str]:
        """Get error message from page"""
        try:
            if self.browser.is_visible(SELECTORS["login_error"], timeout=2000):
                return self.browser.get_text(SELECTORS["login_error"])
        except Exception:
            pass
        return None
    
    def _discover_page_elements(self):
        """
        Discover and log all interactive elements on the current page.
        Helps identify the correct selectors for DistroKid's upload form.
        """
        self._log("─" * 40)
        self._log("PAGE DISCOVERY - Interactive elements found:")
        self._log("─" * 40)
        
        try:
            # Discover text inputs
            inputs = self.browser.page.evaluate("""
                () => {
                    const results = [];
                    const inputs = document.querySelectorAll('input:not([type="hidden"])');
                    inputs.forEach((el, i) => {
                        if (i < 30) {
                            results.push({
                                tag: 'input',
                                type: el.type || 'text',
                                name: el.name || '',
                                id: el.id || '',
                                placeholder: el.placeholder || '',
                                className: el.className ? el.className.substring(0, 60) : '',
                                accept: el.accept || '',
                                visible: el.offsetParent !== null
                            });
                        }
                    });
                    return results;
                }
            """)
            
            if inputs:
                self._log(f"  INPUTS ({len(inputs)} found):")
                for inp in inputs:
                    if inp.get('visible', False):
                        parts = []
                        if inp['type']: parts.append(f"type={inp['type']}")
                        if inp['name']: parts.append(f"name='{inp['name']}'")
                        if inp['id']: parts.append(f"id='{inp['id']}'")
                        if inp['placeholder']: parts.append(f"placeholder='{inp['placeholder']}'")
                        if inp['accept']: parts.append(f"accept='{inp['accept']}'")
                        if inp['className']: parts.append(f"class='{inp['className']}'")
                        self._log(f"    <input {' '.join(parts)}>")
            
            # Discover selects/dropdowns
            selects = self.browser.page.evaluate("""
                () => {
                    const results = [];
                    const selects = document.querySelectorAll('select');
                    selects.forEach((el, i) => {
                        if (i < 15) {
                            const options = Array.from(el.options).slice(0, 5).map(o => o.text);
                            results.push({
                                name: el.name || '',
                                id: el.id || '',
                                className: el.className ? el.className.substring(0, 60) : '',
                                optionCount: el.options.length,
                                sampleOptions: options,
                                visible: el.offsetParent !== null
                            });
                        }
                    });
                    return results;
                }
            """)
            
            if selects:
                self._log(f"  DROPDOWNS ({len(selects)} found):")
                for sel in selects:
                    if sel.get('visible', False):
                        parts = []
                        if sel['name']: parts.append(f"name='{sel['name']}'")
                        if sel['id']: parts.append(f"id='{sel['id']}'")
                        if sel['className']: parts.append(f"class='{sel['className']}'")
                        parts.append(f"options={sel['optionCount']}")
                        self._log(f"    <select {' '.join(parts)}>")
                        if sel['sampleOptions']:
                            self._log(f"      First options: {sel['sampleOptions']}")
            
            # Discover buttons
            buttons = self.browser.page.evaluate("""
                () => {
                    const results = [];
                    const btns = document.querySelectorAll('button, input[type="submit"], a.btn, [role="button"]');
                    btns.forEach((el, i) => {
                        if (i < 20) {
                            results.push({
                                tag: el.tagName.toLowerCase(),
                                text: (el.textContent || '').trim().substring(0, 40),
                                type: el.type || '',
                                id: el.id || '',
                                className: el.className ? el.className.substring(0, 60) : '',
                                href: el.href || '',
                                visible: el.offsetParent !== null
                            });
                        }
                    });
                    return results;
                }
            """)
            
            if buttons:
                self._log(f"  BUTTONS ({len(buttons)} found):")
                for btn in buttons:
                    if btn.get('visible', False) and btn.get('text'):
                        parts = []
                        parts.append(f"'{btn['text']}'")
                        if btn['id']: parts.append(f"id='{btn['id']}'")
                        if btn['type']: parts.append(f"type={btn['type']}")
                        if btn['className']: parts.append(f"class='{btn['className']}'")
                        self._log(f"    <{btn['tag']} {' '.join(parts)}>")
            
            # Discover textareas
            textareas = self.browser.page.evaluate("""
                () => {
                    const results = [];
                    const areas = document.querySelectorAll('textarea');
                    areas.forEach((el, i) => {
                        if (i < 10) {
                            results.push({
                                name: el.name || '',
                                id: el.id || '',
                                placeholder: el.placeholder || '',
                                visible: el.offsetParent !== null
                            });
                        }
                    });
                    return results;
                }
            """)
            
            if textareas:
                self._log(f"  TEXTAREAS ({len(textareas)} found):")
                for ta in textareas:
                    if ta.get('visible', False):
                        parts = []
                        if ta['name']: parts.append(f"name='{ta['name']}'")
                        if ta['id']: parts.append(f"id='{ta['id']}'")
                        if ta['placeholder']: parts.append(f"placeholder='{ta['placeholder']}'")
                        self._log(f"    <textarea {' '.join(parts)}>")
            
            # Discover file inputs specifically
            file_inputs = self.browser.page.evaluate("""
                () => {
                    const results = [];
                    const inputs = document.querySelectorAll('input[type="file"]');
                    inputs.forEach((el, i) => {
                        results.push({
                            name: el.name || '',
                            id: el.id || '',
                            accept: el.accept || '',
                            multiple: el.multiple,
                            className: el.className ? el.className.substring(0, 60) : ''
                        });
                    });
                    return results;
                }
            """)
            
            if file_inputs:
                self._log(f"  FILE INPUTS ({len(file_inputs)} found):")
                for fi in file_inputs:
                    parts = []
                    if fi['name']: parts.append(f"name='{fi['name']}'")
                    if fi['id']: parts.append(f"id='{fi['id']}'")
                    if fi['accept']: parts.append(f"accept='{fi['accept']}'")
                    if fi['multiple']: parts.append("multiple")
                    if fi['className']: parts.append(f"class='{fi['className']}'")
                    self._log(f"    <input type='file' {' '.join(parts)}>")
            
            # Log page title
            title = self.browser.page.title()
            self._log(f"  Page title: '{title}'")
            
        except Exception as e:
            self._log(f"  Discovery error: {e}", "warning")
        
        self._log("─" * 40)
    
    def navigate_to_upload(self):
        """Navigate to upload page"""
        if not self._is_logged_in:
            raise DistroKidError("Not logged in")
        
        self._log("Navigating to upload page (https://distrokid.com/new/)...")
        self.browser.navigate(DISTROKID_UPLOAD_URL)
        time.sleep(5)
        self.browser.wait_for_load()
        
        current_url = self.browser.page.url
        self._log(f"Current URL: {current_url}")
        
        # Check if we actually landed on the upload page
        if "new" not in current_url and "upload" not in current_url:
            self._log(f"WARNING: Expected upload page but landed on: {current_url}", "warning")
            self._log("Trying direct navigation again...")
            self.browser.navigate("https://distrokid.com/new/")
            time.sleep(5)
            current_url = self.browser.page.url
            self._log(f"Second attempt URL: {current_url}")
        
        self._log("Upload page loaded - scanning for form elements...")
        
        # Discover page elements
        self._discover_page_elements()
    
    def fill_album_details(
        self,
        album_title: str,
        artist_name: str,
        genre: str,
        subgenre: str,
        release_date: Optional[str] = None
    ):
        """
        Fill album details on upload form.
        
        Args:
            album_title: Album title (directory name)
            artist_name: Artist name
            genre: Primary genre
            subgenre: Subgenre
            release_date: Optional release date (YYYY-MM-DD)
        """
        self._log(f"Filling album details: '{album_title}' by '{artist_name}'")
        self._log(f"  Genre: {genre} / {subgenre}")
        
        # Fill album title
        self._log("  Looking for album title field...")
        try:
            self.browser.fill(SELECTORS["album_title"], album_title)
            self._log("  ✓ Album title filled")
        except Exception as e:
            self._log(f"  ✗ Could not find album title field: {e}", "warning")
            self._log(f"    Tried selectors: {SELECTORS['album_title']}")
        
        # Fill artist name
        self._log("  Looking for artist name field...")
        try:
            self.browser.fill(SELECTORS["artist_name"], artist_name)
            self._log("  ✓ Artist name filled")
        except Exception as e:
            self._log(f"  ✗ Could not find artist name field: {e}", "warning")
            self._log(f"    Tried selectors: {SELECTORS['artist_name']}")
        
        # Select genre
        self._log("  Looking for genre dropdown...")
        try:
            self.browser.select_option(SELECTORS["genre_select"], genre)
            time.sleep(1)
            self._log(f"  ✓ Genre set to: {genre}")
        except Exception as e:
            self._log(f"  ✗ Could not find genre dropdown: {e}", "warning")
        
        # Select subgenre
        self._log("  Looking for subgenre dropdown...")
        try:
            self.browser.select_option(SELECTORS["subgenre_select"], subgenre)
            self._log(f"  ✓ Subgenre set to: {subgenre}")
        except Exception as e:
            self._log(f"  ✗ Could not find subgenre dropdown: {e}", "warning")
        
        # Fill release date if provided
        if release_date:
            self._log(f"  Setting release date: {release_date}")
            try:
                self.browser.fill(SELECTORS["release_date"], release_date)
                self._log("  ✓ Release date filled")
            except Exception as e:
                self._log(f"  ✗ Could not find release date field: {e}", "warning")
        
        self._log("Album details complete")
    
    def upload_track(self, track_number: int, wav_path: Path, title: str) -> bool:
        """
        Upload a single track.
        
        Args:
            track_number: Track number (1-based)
            wav_path: Path to audio file (WAV or MP3)
            title: Track title
        
        Returns:
            True if upload successful
        """
        try:
            self._log(f"  Track {track_number}: '{title}'")
            self._log(f"    File: {wav_path}")
            self._log(f"    Size: {wav_path.stat().st_size / (1024*1024):.1f} MB")
            
            # Look for file input
            self._log(f"    Looking for file upload input...")
            self.browser.upload_file(
                SELECTORS["track_upload"],
                wav_path,
                timeout=60000  # Longer timeout for file upload
            )
            self._log(f"    ✓ File selected for upload")
            
            # Wait for upload to process
            self._log(f"    Waiting for upload to process...")
            time.sleep(3)
            
            # Fill track title
            self._log(f"    Setting track title...")
            try:
                title_selector = f"{SELECTORS['track_title']}:nth-of-type({track_number})"
                self.browser.fill(title_selector, title)
                self._log(f"    ✓ Track title set")
            except Exception as e:
                self._log(f"    ✗ Could not set track title: {e}", "warning")
            
            self._log(f"  ✓ Track {track_number} complete")
            return True
            
        except Exception as e:
            self._log(f"  ✗ Track {track_number} FAILED: {e}", "error")
            return False
    
    def upload_artwork(self, artwork_path: Path) -> bool:
        """
        Upload album artwork.
        
        Args:
            artwork_path: Path to artwork image
        
        Returns:
            True if upload successful
        """
        try:
            self._log(f"Uploading artwork: {artwork_path.name} ({artwork_path.stat().st_size / 1024:.0f} KB)")
            
            self.browser.upload_file(
                SELECTORS["artwork_upload"],
                artwork_path,
                timeout=30000
            )
            
            # Wait for upload
            time.sleep(2)
            
            self._log("✓ Artwork uploaded")
            return True
            
        except Exception as e:
            self._log(f"✗ Artwork upload failed: {e}", "warning")
            return False
    
    def submit_upload(self) -> bool:
        """
        Submit the upload form and handle the full post-submission flow:
        1. Click Continue (#doneButton) on the form page
        2. Wait for upload progress ("Looks good?" page with track percentages)
        3. Wait for redirect to /new/mixea/ page
        4. Select "Use my originals" radio and click Continue
        5. Wait for redirect to /new/done/ page → success!
        
        Returns:
            True if submission successful
        """
        try:
            self._log("Submitting upload form...")
            
            # Step 1: Click the Continue/Done button
            done_btn = self.browser.page.locator("#doneButton")
            if done_btn.count() > 0:
                done_btn.click()
                self._log("  ✓ Continue button clicked")
            else:
                fallbacks = [
                    "input[value='Continue']",
                    "input.distroDoneButtonWithAPI",
                ]
                clicked = False
                for selector in fallbacks:
                    try:
                        btn = self.browser.page.locator(selector)
                        if btn.count() > 0 and btn.first.is_visible(timeout=3000):
                            btn.first.click()
                            clicked = True
                            break
                    except Exception:
                        continue
                if not clicked:
                    self._log("  ✗ Could not find Continue button", "error")
                    return False
            
            # Step 2: Wait for upload progress to complete
            # The page shows "Looks good?" with track upload percentages
            # Wait for the URL to change away from /new/ (can take minutes for large albums)
            self._log("  Waiting for upload processing (this may take a few minutes)...")
            
            max_wait = 600  # 10 minutes max
            start_time = time.time()
            while time.time() - start_time < max_wait:
                time.sleep(5)
                current_url = self.browser.page.url
                
                # Success: reached the done page
                if "/new/done/" in current_url:
                    self._log("✓ Upload complete! Reached done page.")
                    return True
                
                # Intermediate: reached the mixea/enhance page
                if "/new/mixea/" in current_url or "/new/enhance/" in current_url:
                    self._log("  Reached enhancement options page...")
                    break
                
                # Still on /new/ — check for validation errors
                try:
                    swal = self.browser.page.locator(".swal2-popup")
                    if swal.count() > 0 and swal.first.is_visible(timeout=1000):
                        error_text = swal.first.text_content()
                        if "Validation" in error_text or "Error" in error_text:
                            self._log(f"  ✗ Validation error: {error_text[:200]}", "error")
                            # Click OK to dismiss
                            ok_btn = self.browser.page.locator("button.swal2-confirm")
                            if ok_btn.count() > 0:
                                ok_btn.first.click()
                                time.sleep(1)
                            return False
                except Exception:
                    pass
                
                # Log progress
                if int(time.time() - start_time) % 30 == 0:
                    self._log(f"  Still uploading... ({int(time.time() - start_time)}s elapsed)")
            
            # Step 3: Handle the mixea/enhance page — select "Use my originals"
            current_url = self.browser.page.url
            if "/new/mixea/" in current_url or "/new/enhance/" in current_url:
                self._log("  Selecting 'Use my originals'...")
                time.sleep(2)
                
                # Click the "Use my originals" radio (value="0")
                try:
                    radio = self.browser.page.locator("input[type='radio'][name='variant'][value='0']")
                    if radio.count() > 0:
                        radio.first.dispatch_event("click")
                        self._log("  ✓ Selected 'Use my originals'")
                    else:
                        # Try clicking the text
                        use_originals = self.browser.page.get_by_text("Use my originals", exact=False)
                        if use_originals.count() > 0:
                            use_originals.first.click()
                            self._log("  ✓ Selected 'Use my originals' via text")
                except Exception as e:
                    self._log(f"  Could not select 'Use my originals': {e}")
                
                time.sleep(1)
                
                # Click the Continue button on this page
                try:
                    continue_btn = self.browser.page.locator("button.submit-button")
                    if continue_btn.count() > 0:
                        continue_btn.first.click()
                        self._log("  ✓ Clicked Continue on enhancement page")
                    else:
                        continue_btn = self.browser.page.get_by_text("Continue", exact=True)
                        if continue_btn.count() > 0:
                            continue_btn.first.click()
                except Exception as e:
                    self._log(f"  Could not click Continue: {e}")
                
                # Wait for redirect to /new/done/
                self._log("  Waiting for final confirmation...")
                try:
                    self.browser.page.wait_for_url("**/new/done/**", timeout=30000)
                    self._log("✓ Upload complete! Music is on its way!")
                    return True
                except Exception:
                    current_url = self.browser.page.url
                    if "/new/done/" in current_url:
                        self._log("✓ Upload complete!")
                        return True
                    self._log(f"  Final URL: {current_url}")
            
            # Check if we ended up on done page
            current_url = self.browser.page.url
            if "/new/done/" in current_url:
                self._log("✓ Upload complete!")
                return True
            
            self._log(f"✗ Upload may have failed. Final URL: {current_url}", "error")
            return False
            
        except Exception as e:
            self._log(f"✗ Submit failed: {e}", "error")
            return False
    
    def _check_upload_success(self) -> bool:
        """Check if upload was successful"""
        try:
            if self.browser.is_visible(SELECTORS["success_message"], timeout=5000):
                return True
            
            # Check URL for success indicators
            current_url = self.browser.page.url
            if "success" in current_url or "thank" in current_url:
                return True
            
            return False
            
        except Exception:
            return False
    
    def _get_upload_error(self) -> Optional[str]:
        """Get upload error message"""
        try:
            if self.browser.is_visible(SELECTORS["error_message"], timeout=2000):
                return self.browser.get_text(SELECTORS["error_message"])
        except Exception:
            pass
        return None
    
    def upload_album(
        self,
        album_name: str,
        artist_name: str,
        tracks: list[tuple[int, Path, str]],
        artwork_path: Optional[Path] = None,
        genre: str = "Electronic",
        subgenre: str = "House",
        release_date: Optional[str] = None,
        auto_submit: bool = False
    ) -> bool:
        """
        Upload complete album.
        
        Args:
            album_name: Album title
            artist_name: Artist name
            tracks: List of (track_number, file_path, title) tuples
            artwork_path: Optional artwork path
            genre: Primary genre
            subgenre: Subgenre
            release_date: Optional release date
            auto_submit: If True, auto-submit after upload
        
        Returns:
            True if upload successful
        """
        try:
            self._log(f"{'='*50}")
            self._log(f"UPLOADING ALBUM: '{album_name}'")
            self._log(f"  Artist: {artist_name}")
            self._log(f"  Tracks: {len(tracks)}")
            self._log(f"  Genre: {genre} / {subgenre}")
            self._log(f"  Auto-submit: {auto_submit}")
            if artwork_path:
                self._log(f"  Artwork: {artwork_path.name}")
            self._log(f"{'='*50}")
            
            # Step 1: Navigate to upload page
            self._log("[Step 1/5] Navigating to upload page...")
            self.navigate_to_upload()
            self._log("✓ Upload page ready")
            
            # Step 2: Fill album details
            self._log("[Step 2/5] Filling album details...")
            self.fill_album_details(
                album_title=album_name,
                artist_name=artist_name,
                genre=genre,
                subgenre=subgenre,
                release_date=release_date
            )
            
            # Step 3: Upload tracks
            self._log(f"[Step 3/5] Uploading {len(tracks)} track(s)...")
            total_tracks = len(tracks)
            for i, (track_number, file_path, title) in enumerate(tracks, 1):
                self._update_progress(i, total_tracks, f"Uploading: {title}")
                self._log(f"  [{i}/{total_tracks}] Uploading track...")
                
                if not self.upload_track(track_number, file_path, title):
                    self._log(f"✗ FAILED at track {track_number} - aborting album upload", "error")
                    raise DistroKidUploadError(f"Failed to upload track {track_number}: {title}")
            
            self._log(f"✓ All {total_tracks} tracks uploaded")
            
            # Step 4: Upload artwork
            self._log("[Step 4/5] Uploading artwork...")
            if artwork_path and artwork_path.exists():
                self.upload_artwork(artwork_path)
            else:
                self._log("  No artwork provided or file not found - skipping")
            
            # Step 5: Submit if auto_submit
            if auto_submit:
                self._log("[Step 5/5] Auto-submitting...")
                if not self.submit_upload():
                    raise DistroKidUploadError("Failed to submit upload")
            else:
                self._log("[Step 5/5] Auto-submit disabled - upload ready for manual review")
                self._log("  Please review the upload on DistroKid and submit manually")
            
            self._log(f"{'='*50}")
            self._log(f"✓ Album '{album_name}' upload COMPLETE")
            self._log(f"{'='*50}")
            return True
            
        except DistroKidUploadError:
            raise
        except Exception as e:
            self._log(f"✗ Album upload FAILED: {e}", "error")
            raise DistroKidUploadError(f"Upload failed: {e}")
    
    def logout(self):
        """Logout from DistroKid"""
        try:
            self._log("Logging out...")
            # Implementation depends on DistroKid's logout mechanism
            # This is a placeholder
            self._is_logged_in = False
        except Exception as e:
            self._log(f"Error during logout: {e}", "warning")
