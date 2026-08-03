"""
Form Automator Module

Orchestrates the DistroKid upload questionnaire automation.
Walks through the form step-by-step using ElementResolver to interact with each section.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from features.distrokid.services.element_resolver import ElementResolver, ElementNotFoundError
from features.distrokid.services.report import AutomationReporter
from features.distrokid.services.track_uploader import TrackUploader
from features.distrokid.lib.distrokid_settings import UploadFormConfig
from features.distrokid.models.distrokid_models import Album

logger = logging.getLogger(__name__)


class SessionExpiredError(Exception):
    """Raised when the browser session has expired (redirected to login)."""

    def __init__(self, url: str = ""):
        self.url = url
        super().__init__(f"Session expired — redirected to login page: {url}")


class PageLoadError(Exception):
    """Raised when a page section fails to load within the timeout."""

    def __init__(self, section: str = "", timeout: int = 0):
        self.section = section
        self.timeout = timeout
        super().__init__(
            f"Page section '{section}' did not load within {timeout}ms"
        )


@dataclass
class FormProgress:
    """Tracks automation progress through questionnaire sections."""

    total_steps: int
    completed_steps: int = 0
    current_step: str = ""
    errors: list = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.completed_steps >= self.total_steps and not self.errors


class FormAutomator:
    """Orchestrates the DistroKid upload questionnaire automation."""

    # Total number of major steps in the questionnaire flow
    _TOTAL_STEPS = 15

    def __init__(
        self,
        page: Page,
        config: UploadFormConfig,
        resolver: ElementResolver,
        on_log: Callable[[str], None] = None,
        on_progress: Callable[[FormProgress], None] = None,
        report_dir: Optional[Path] = None,
    ):
        """
        Initialize FormAutomator.

        Args:
            page: Playwright Page instance for browser interaction.
            config: UploadFormConfig with all questionnaire field values.
            resolver: ElementResolver instance for finding form elements.
            on_log: Callable for logging messages to the UI.
            on_progress: Callable receiving FormProgress updates.
            report_dir: Directory to save automation reports. Defaults to output/.
        """
        self.page = page
        self.config = config
        self.resolver = resolver
        self._on_log = on_log or (lambda msg: None)
        self._on_progress = on_progress or (lambda p: None)
        self._progress = FormProgress(total_steps=self._TOTAL_STEPS)
        self._report_dir = report_dir
        self._reporter: Optional[AutomationReporter] = None

    def automate_questionnaire(self, album: Album) -> bool:
        """Run the full questionnaire automation.

        Calls each section method in the order they appear on the DistroKid
        upload page. Reports progress after each major section.
        Generates an automation report tracking any issues encountered.

        Args:
            album: Album instance with tracks, thumbnail, and name.

        Returns:
            True on successful completion of all sections, False on failure.
        """
        # Initialize the automation reporter for this run
        self._reporter = AutomationReporter(
            album_name=album.name,
            report_dir=self._report_dir,
        )
        self._reporter.start()

        success = False
        try:
            self._log("Starting questionnaire automation...")
            self._check_page_state()

            # CRITICAL: Override DistroKid's socialMediaPackModalClick function
            # so the Social Media Pack modal can NEVER appear during automation.
            # DistroKid auto-checks this checkbox every time a track is uploaded.
            self.page.evaluate("""
                window._originalSocialMediaPackModalClick = window.socialMediaPackModalClick;
                window.socialMediaPackModalClick = function(el) {
                    // Prevent the checkbox from being checked and block the modal
                    if (el) { el.checked = false; }
                    return false;
                };
            """)
            self._log("Disabled Social Media Pack auto-check.")

            # Dismiss cookie consent banner if present (Osano)
            try:
                cookie_close = self.page.locator(".osano-cm-dialog__close")
                if cookie_close.count() > 0 and cookie_close.first.is_visible(timeout=2000):
                    cookie_close.first.click()
                    self._log("Dismissed cookie consent banner.")
                    time.sleep(0.5)
            except Exception:
                pass

            # Section 1: Song count (dynamic — based on actual track count)
            self._run_section("Select song count", lambda: self._select_song_count(album))

            # DEBUG: Check if Social Media Pack got checked
            smp_state = self.page.evaluate(
                "document.getElementById('socialmediapack') ? document.getElementById('socialmediapack').checked : 'not found'"
            )
            self._log(f"  [DEBUG] Social Media Pack checked after song count: {smp_state}")

            # Dismiss Social Media Pack modal if it appeared
            self._dismiss_social_media_pack()

            # Section 2: Previously released
            self._run_section("Answer previously released", self._answer_previously_released)

            # Section 3: Upgrade prompt
            self._run_section("Dismiss upgrade prompt", self._dismiss_upgrade_prompt)

            # Section 4: Instagram
            self._run_section("Answer Instagram question", self._answer_instagram)

            # Section 5: Facebook
            self._run_section("Answer Facebook question", self._answer_facebook)

            # Section 6: Release date
            self._run_section("Set release date", self._set_release_date)

            # Section 7: Language
            self._run_section("Select language", self._select_language)

            # Section 8: Genre
            self._run_section("Select genre", self._select_genre)

            # Section 9: Artwork upload
            self._run_section(
                "Upload artwork",
                lambda: self._upload_artwork(album.thumbnail),
            )

            # Brief wait + dismiss any lingering modals before album title
            time.sleep(1)
            self._dismiss_social_media_pack()

            # Section 10: Album title (skip for singles — DistroKid hides it)
            if len(album.tracks) > 1:
                self._run_section("Fill album title", lambda: self._fill_album_title(album))
            else:
                self._log("Single track — skipping album title (not required by DistroKid)")
                # Adjust total steps since we're skipping one
                self._progress.total_steps -= 1

            # Wait for DistroKid to fully initialize track upload slots
            time.sleep(3)
            
            # Scroll to track 1 area to ensure it's in viewport
            try:
                self.page.locator("#js-track-upload-1").scroll_into_view_if_needed()
                time.sleep(1)
            except Exception:
                pass

            # Section 11: Track uploads
            self._run_section("Upload tracks", lambda: self._upload_tracks(album))

            # Section 11: Apple Music credits
            self._run_section("Fill Apple Music credits", self._fill_apple_music_credits)

            # Section 12: Producer credits
            self._run_section("Fill producer credits", self._fill_producer_credits)

            # Section 13: Extras section
            self._run_section("Handle extras section", self._handle_extras_section)

            # Section 14: Mandatory checkboxes
            self._run_section("Handle mandatory checkboxes", self._handle_mandatory_checkboxes)

            self._log("Questionnaire automation completed successfully.")
            success = True
            return True

        except SessionExpiredError as e:
            self._log(f"ERROR: Session expired — {e}")
            self._progress.errors.append(str(e))
            self._reporter.record_issue(
                severity="blocker",
                category="unexpected_state",
                step=self._progress.current_step,
                description=f"Session expired — redirected to login: {e.url}",
                page_url=e.url,
                suggestion="Re-login required. Check if cookies/session expired.",
            )
            self._report_progress()
            return False

        except PageLoadError as e:
            self._log(f"ERROR: Page load failure — {e}")
            self._progress.errors.append(str(e))
            self._reporter.record_issue(
                severity="blocker",
                category="timeout",
                step=self._progress.current_step,
                description=f"Page section failed to load: {e.section}",
                page_url=self.page.url,
                suggestion="DistroKid page may have changed layout or is loading slowly. Increase element_timeout or check network.",
            )
            self._report_progress()
            return False

        except Exception as e:
            self._log(f"ERROR: Unexpected failure — {e}")
            self._progress.errors.append(str(e))
            self._reporter.record_issue(
                severity="blocker",
                category="unexpected_state",
                step=self._progress.current_step,
                description=f"Unexpected error: {e}",
                page_url=self.page.url if self.page else "",
                suggestion="Check logs for stack trace. This may indicate a DistroKid page change.",
            )
            self._report_progress()
            return False

        finally:
            # Always save the automation report
            self._reporter.finish(
                success=success,
                steps_attempted=self._TOTAL_STEPS,
                steps_completed=self._progress.completed_steps,
            )
            report_path = self._reporter.save()
            summary = self._reporter.get_summary()
            self._log(f"Automation report saved: {report_path}")
            if self._reporter.get_report().has_issues:
                self._log(summary)

    # --- Section methods ---

    def _select_song_count(self, album: Album) -> None:
        """Select the song count from the dropdown.
        
        DistroKid uses a <select id='howManySongsOnThisAlbum'> with options like
        "1 song (a single)", "2 songs", "3 songs", etc.
        """
        song_count = len(album.tracks)
        self._log(f"Selecting song count: {song_count} (from album track count)")

        # Build the expected option text
        if song_count == 1:
            option_text = "1 song (a single)"
        else:
            option_text = f"{song_count} songs"

        # Use the known select element directly
        dropdown = self.page.locator("#howManySongsOnThisAlbum")
        if dropdown.count() > 0:
            dropdown.select_option(label=option_text)
            self._log(f"  Selected: '{option_text}'")
        else:
            # Fallback: try by name
            dropdown = self.page.locator("select[name='howmanysongs']")
            if dropdown.count() > 0:
                dropdown.select_option(label=option_text)
                self._log(f"  Selected via name attr: '{option_text}'")
            else:
                raise ElementNotFoundError(
                    description=f"Song count dropdown for {song_count}",
                    strategies_attempted=["id_selector", "name_selector"],
                    page_url=self.page.url,
                )

    def _dismiss_social_media_pack(self) -> None:
        """Dismiss the Social Media Pack modal if it appeared.
        
        We do NOT touch the checkbox at all. We only look for the modal 
        and click Cancel if it's showing. If no modal, we do nothing.
        """
        want_social_pack = getattr(self.config, 'social_media_pack', False)
        
        if not want_social_pack:
            self._log("Checking for Social Media Pack modal...")
            try:
                cancel_btn = self.page.get_by_text("Cancel", exact=True)
                if cancel_btn.count() > 0 and cancel_btn.first.is_visible(timeout=2000):
                    cancel_btn.first.click()
                    self._log("  Dismissed Social Media Pack modal via Cancel.")
                    time.sleep(1)
                else:
                    self._log("  No modal visible, continuing.")
            except Exception:
                self._log("  No modal found, continuing.")
        else:
            # User wants Social Media Pack — confirm the modal if showing
            self._log("Confirming Social Media Pack...")
            try:
                confirm = self.page.get_by_text("Yes, I understand and confirm", exact=False)
                if confirm.count() > 0 and confirm.first.is_visible(timeout=3000):
                    confirm.first.click()
                    songwriter = self.page.get_by_text("only songwriter", exact=False)
                    if songwriter.count() > 0:
                        songwriter.first.click()
                    time.sleep(0.5)
                    continue_btn = self.page.get_by_text("Continue", exact=True)
                    if continue_btn.count() > 0:
                        continue_btn.first.click()
                        self._log("  Social Media Pack confirmed.")
                        time.sleep(1)
            except Exception as e:
                self._log(f"  Error with Social Media Pack: {e}")

    def _answer_previously_released(self) -> None:
        """Answer the 'previously released' question.
        
        DistroKid uses radio buttons with class 'distroPreviouslyReleased'.
        We use JavaScript to select the correct one to avoid mis-clicking.
        """
        answer = "Yes" if self.config.previously_released else "No"
        self._log(f"Answering previously released: {answer}")

        # Use JavaScript to click the correct radio to avoid force-click issues
        # First radio (index 0) = No, Second radio (index 1) = Yes
        radio_index = 1 if self.config.previously_released else 0
        
        clicked = self.page.evaluate(f"""
            (() => {{
                var radios = document.querySelectorAll('input.distroPreviouslyReleased');
                if (radios.length >= 2) {{
                    radios[{radio_index}].click();
                    return true;
                }}
                return false;
            }})()
        """)
        
        if clicked:
            self._log(f"  Selected '{answer}' via JS click.")
        else:
            # Fallback to text-based resolution
            radio = self.resolver.resolve_radio_option(
                question_text="previously released",
                option_text=answer,
            )
            radio.click(force=True)

    def _dismiss_upgrade_prompt(self) -> None:
        """Dismiss the 'upgrade to ultimate' prompt."""
        self._log("Dismissing upgrade prompt...")
        try:
            dismiss_btn = self.resolver.resolve(
                description="Upgrade prompt dismiss",
                element_type="button",
                text="No thanks",
                near_text="upgrade",
            )
            dismiss_btn.click()
        except ElementNotFoundError:
            # Prompt may not appear for all users
            self._log("Upgrade prompt not found, skipping.")

    def _answer_instagram(self) -> None:
        """Answer the 'artist on Instagram' question from config.
        
        Uses JS to find and click the radio to avoid pointer interception
        from the Social Media Pack section overlay.
        """
        answer = "Yes" if self.config.artist_on_instagram else "No"
        self._log(f"Answering Instagram question: {answer}")

        # Use JavaScript to click the correct radio — avoids overlay interception
        clicked = self.page.evaluate(f"""
            (() => {{
                // Find all elements containing "Instagram" text that have radio inputs nearby
                var labels = document.querySelectorAll('label');
                for (var i = 0; i < labels.length; i++) {{
                    var label = labels[i];
                    if (label.textContent.includes('Instagram') && label.textContent.includes('{answer}')) {{
                        var radio = label.querySelector('input[type="radio"]') || 
                                    document.getElementById(label.getAttribute('for'));
                        if (radio) {{ radio.click(); return true; }}
                    }}
                }}
                // Fallback: find radio near "Instagram" text
                var elements = document.querySelectorAll('*');
                for (var i = 0; i < elements.length; i++) {{
                    if (elements[i].childNodes.length === 1 && 
                        elements[i].textContent.trim() === '{answer}' &&
                        elements[i].closest('[class*="instagram" i], [class*="Instagram" i], :has(> *:contains("Instagram"))')) {{
                        elements[i].click();
                        return true;
                    }}
                }}
                return false;
            }})()
        """)
        
        if not clicked:
            # Fallback: try resolver but skip if fails
            try:
                radio = self.resolver.resolve_radio_option(
                    question_text="Instagram",
                    option_text=answer,
                )
                radio.dispatch_event("click")
            except ElementNotFoundError:
                self._log("  Instagram question not found, skipping.")

    def _answer_facebook(self) -> None:
        """Answer the 'artist on Facebook' question from config.
        
        Uses JS to find and click the radio to avoid pointer interception
        from the Social Media Pack section overlay.
        """
        answer = "Yes" if self.config.artist_on_facebook else "No"
        self._log(f"Answering Facebook question: {answer}")

        # Use JavaScript to click — avoids overlay interception
        clicked = self.page.evaluate(f"""
            (() => {{
                var labels = document.querySelectorAll('label');
                for (var i = 0; i < labels.length; i++) {{
                    var label = labels[i];
                    if (label.textContent.includes('Facebook') && label.textContent.includes('{answer}')) {{
                        var radio = label.querySelector('input[type="radio"]') || 
                                    document.getElementById(label.getAttribute('for'));
                        if (radio) {{ radio.click(); return true; }}
                    }}
                }}
                return false;
            }})()
        """)
        
        if not clicked:
            try:
                radio = self.resolver.resolve_radio_option(
                    question_text="Facebook",
                    option_text=answer,
                )
                radio.dispatch_event("click")
            except ElementNotFoundError:
                self._log("  Facebook question not found, skipping.")

    def _set_release_date(self) -> None:
        """Set the release date based on config mode."""
        if self.config.release_date_mode == "custom" and self.config.custom_release_date:
            self._log(f"Setting custom release date: {self.config.custom_release_date}")
            date_input = self.resolver.resolve(
                description="Release date input",
                element_type="text_input",
                label="release date",
                near_text="release date",
            )
            date_input.fill(self.config.custom_release_date)
        else:
            self._log("Leaving release date at default (ASAP).")
            # Default mode — no interaction needed

    def _select_language(self) -> None:
        """Select the configured language from the dropdown.
        
        DistroKid uses <select id='language' name='language'>.
        """
        self._log(f"Selecting language: {self.config.language}")

        dropdown = self.page.locator("#language")
        if dropdown.count() > 0:
            dropdown.select_option(label=self.config.language)
            self._log(f"  Selected language: {self.config.language}")
        else:
            # Fallback
            dropdown = self.page.locator("select[name='language']")
            dropdown.select_option(label=self.config.language)

    def _select_genre(self) -> None:
        """Select the primary genre, subgenre, and optional secondary genre.
        
        DistroKid uses <select> dropdowns for genre. Our app's settings UI
        uses free text inputs, so the user-typed value may not exactly match
        a dropdown option label. We handle this with case-insensitive matching.
        """
        self._log(f"Selecting genre: {self.config.primary_genre} / {self.config.subgenre}")

        # 1. Primary genre — use JS for case-insensitive matching against <select> options
        genre_selected = self.page.evaluate(f"""
            (() => {{
                var sel = document.getElementById('genrePrimary') || 
                          document.querySelector("select[name='genre1']");
                if (!sel || sel.tagName !== 'SELECT') return 'no_dropdown';
                
                var target = '{self.config.primary_genre}'.trim().toLowerCase();
                
                // Exact match first
                for (var i = 0; i < sel.options.length; i++) {{
                    if (sel.options[i].text.trim().toLowerCase() === target) {{
                        sel.selectedIndex = i;
                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return sel.options[i].text;
                    }}
                }}
                
                // Partial/contains match
                for (var i = 0; i < sel.options.length; i++) {{
                    var optText = sel.options[i].text.trim().toLowerCase();
                    if (optText.includes(target) || target.includes(optText)) {{
                        sel.selectedIndex = i;
                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return sel.options[i].text;
                    }}
                }}
                
                return 'not_found';
            }})()
        """)

        if genre_selected and genre_selected not in ('no_dropdown', 'not_found'):
            self._log(f"  Primary genre: {genre_selected}")
        elif genre_selected == 'not_found':
            self._log(f"  ERROR: Primary genre '{self.config.primary_genre}' not found in DistroKid dropdown!")
            self._log(f"  Available options will be logged for debugging...")
            # Log available options for user
            options = self.page.evaluate("""
                (() => {
                    var sel = document.getElementById('genrePrimary') || 
                              document.querySelector("select[name='genre1']");
                    if (!sel) return [];
                    return Array.from(sel.options).map(o => o.text).filter(t => t.length > 0);
                })()
            """)
            if options:
                self._log(f"  Available genres: {', '.join(options)}")
            if self._reporter:
                self._reporter.record_issue(
                    severity="blocker",
                    category="field_missed",
                    step="Select genre",
                    description=f"Primary genre '{self.config.primary_genre}' does not match any DistroKid dropdown option.",
                    page_url=self.page.url,
                    suggestion=f"Update your genre setting to match one of: {', '.join(options) if options else 'unknown'}",
                )
            return
        else:
            self._log(f"  ERROR: Genre dropdown not found on page!")
            return

        # 2. Wait for subgenre dropdown to appear (loads dynamically)
        time.sleep(1.5)

        # Subgenre — find the dynamically-loaded subgenre <select> and match case-insensitively
        if self.config.subgenre:
            selected = self.page.evaluate(f"""
                (() => {{
                    var selects = document.querySelectorAll('select');
                    var knownIds = ['howManySongsOnThisAlbum', 'language', 'genrePrimary', 'genreSecondary'];
                    var knownNames = ['howmanysongs', 'language', 'genre1', 'genre2'];
                    
                    for (var i = 0; i < selects.length; i++) {{
                        var sel = selects[i];
                        if (knownIds.includes(sel.id) || knownNames.includes(sel.name)) continue;
                        if (sel.offsetParent === null) continue;
                        
                        if (sel.options.length > 1) {{
                            var firstOpt = sel.options[0].text.toLowerCase();
                            if (firstOpt.includes('subgenre') || firstOpt.includes('select')) {{
                                var target = '{self.config.subgenre}'.trim().toLowerCase();
                                
                                // Exact match
                                for (var j = 0; j < sel.options.length; j++) {{
                                    if (sel.options[j].text.trim().toLowerCase() === target) {{
                                        sel.selectedIndex = j;
                                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                                        return sel.options[j].text;
                                    }}
                                }}
                                
                                // Partial match
                                for (var j = 0; j < sel.options.length; j++) {{
                                    var optText = sel.options[j].text.trim().toLowerCase();
                                    if (optText.includes(target) || target.includes(optText)) {{
                                        sel.selectedIndex = j;
                                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                                        return sel.options[j].text;
                                    }}
                                }}
                                return 'not_found';
                            }}
                        }}
                    }}
                    return 'no_dropdown';
                }})()
            """)
            
            if selected and selected not in ('not_found', 'no_dropdown'):
                self._log(f"  Subgenre: {selected}")
            elif selected == 'not_found':
                self._log(f"  Subgenre '{self.config.subgenre}' not available for this genre. Skipping.")
            else:
                self._log(f"  Subgenre dropdown not found. Skipping.")

        # 3. Secondary genre (optional)
        secondary_genre = getattr(self.config, 'secondary_genre', '')
        if secondary_genre:
            time.sleep(0.5)
            sec_selected = self.page.evaluate(f"""
                (() => {{
                    var sel = document.getElementById('genreSecondary') || 
                              document.querySelector("select[name='genre2']");
                    if (!sel || sel.tagName !== 'SELECT') return 'no_dropdown';
                    
                    var target = '{secondary_genre}'.trim().toLowerCase();
                    
                    for (var i = 0; i < sel.options.length; i++) {{
                        if (sel.options[i].text.trim().toLowerCase() === target) {{
                            sel.selectedIndex = i;
                            sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return sel.options[i].text;
                        }}
                    }}
                    
                    // Partial match
                    for (var i = 0; i < sel.options.length; i++) {{
                        var optText = sel.options[i].text.trim().toLowerCase();
                        if (optText.includes(target) || target.includes(optText)) {{
                            sel.selectedIndex = i;
                            sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return sel.options[i].text;
                        }}
                    }}
                    return 'not_found';
                }})()
            """)
            
            if sec_selected and sec_selected not in ('not_found', 'no_dropdown'):
                self._log(f"  Secondary genre: {sec_selected}")
            elif sec_selected == 'not_found':
                self._log(f"  Secondary genre '{secondary_genre}' not found in options. Skipping.")
            else:
                self._log(f"  Secondary genre dropdown not found. Skipping.")
        else:
            self._log(f"  Secondary genre: skipped (not configured)")

    def _upload_artwork(self, artwork_path: Optional[Path]) -> None:
        """Upload album artwork, auto-resizing to meet DistroKid requirements.

        DistroKid requires artwork to be at least 3000x3000 pixels (square).
        If the image is too small or not square, we resize/pad it automatically.

        Args:
            artwork_path: Path to the artwork image file, or None if not available.
        """
        if artwork_path is None or not artwork_path.exists():
            self._log("No artwork file found, skipping artwork upload.")
            if self._reporter:
                self._reporter.record_issue(
                    severity="warning",
                    category="field_missed",
                    step="Upload artwork",
                    description="No artwork file found in album directory. Upload will proceed without cover art.",
                    suggestion="Add a .jpg/.png image file to the album folder for cover art.",
                )
            return

        self._log(f"Uploading artwork: {artwork_path.name}")

        # Auto-resize if needed
        upload_path = self._prepare_artwork(artwork_path)

        # DistroKid uses <input type='file' id='artwork' accept='image/*'>
        file_input = self.page.locator("#artwork")
        if file_input.count() == 0:
            file_input = self.page.locator("input[type='file'][accept*='image']")
        file_input.set_input_files(str(upload_path))
        self._log(f"  Artwork uploaded: {upload_path.name}")
        time.sleep(1)
        
        # Dismiss Social Media Pack modal if it appeared after upload
        self._dismiss_social_media_pack()

    def _fill_album_title(self, album: Album) -> None:
        """Fill the album title field.
        
        DistroKid uses: <input id='albumTitleInput' name='albumtitle'>
        May be hidden until scrolled into view or a preceding step completes.
        """
        self._log(f"Filling album title: {album.name}")
        
        title_input = self.page.locator("#albumTitleInput")
        if title_input.count() == 0:
            # Fallback selector
            title_input = self.page.locator("input[name='albumtitle']")
        
        if title_input.count() == 0:
            self._log("  Album title input not found!")
            return
        
        # Scroll into view first — DistroKid may hide it below the fold
        try:
            title_input.scroll_into_view_if_needed(timeout=5000)
            time.sleep(0.5)
        except Exception:
            pass
        
        # Try clicking to focus/reveal it (some fields only become editable after click)
        try:
            title_input.click(timeout=5000)
            time.sleep(0.3)
        except Exception:
            pass
        
        # Clear and fill
        try:
            title_input.fill(album.name, timeout=10000)
            self._log(f"  Album title set: {album.name}")
        except Exception:
            # Last resort: use JavaScript to set the value directly
            try:
                self.page.evaluate(
                    """(title) => {
                        const el = document.querySelector('#albumTitleInput') || 
                                   document.querySelector("input[name='albumtitle']");
                        if (el) {
                            el.value = title;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                        }
                    }""",
                    album.name
                )
                self._log(f"  Album title set via JS: {album.name}")
            except Exception as e:
                self._log(f"  Failed to set album title: {e}")

    def _prepare_artwork(self, artwork_path: Path) -> Path:
        """Prepare artwork to meet DistroKid's requirements (3000x3000 square JPG).
        
        Crops to center square, then resizes to 3000x3000.
        
        Args:
            artwork_path: Original artwork path.
            
        Returns:
            Path to the artwork file ready for upload (original or resized).
        """
        try:
            from PIL import Image
            
            img = Image.open(artwork_path)
            width, height = img.size
            target_size = 3000
            
            self._log(f"  Artwork size: {width}x{height}")
            
            # If already square and large enough, use as-is
            if width >= target_size and height >= target_size and width == height:
                self._log(f"  Artwork already meets requirements ({width}x{height}).")
                return artwork_path
            
            self._log(f"  Cropping and resizing artwork to {target_size}x{target_size}...")
            
            # Crop to center square (use the shorter side)
            if width != height:
                min_dim = min(width, height)
                left = (width - min_dim) // 2
                top = (height - min_dim) // 2
                right = left + min_dim
                bottom = top + min_dim
                img = img.crop((left, top, right, bottom))
                self._log(f"  Cropped to square: {min_dim}x{min_dim}")
            
            # Resize to target
            if img.size[0] != target_size:
                img = img.resize((target_size, target_size), Image.LANCZOS)
                self._log(f"  Resized to {target_size}x{target_size}")
            
            # Save to temp file next to original
            output_path = artwork_path.parent / f"{artwork_path.stem}_3000x3000.jpg"
            img.convert("RGB").save(output_path, "JPEG", quality=95)
            self._log(f"  Saved resized artwork: {output_path.name}")
            return output_path
            
        except ImportError:
            self._log("  WARNING: Pillow not installed — cannot resize artwork. Using original.")
            return artwork_path
        except Exception as e:
            self._log(f"  WARNING: Could not resize artwork: {e}. Using original.")
            return artwork_path

    # --- Placeholder methods (implemented in later tasks) ---

    def _upload_tracks(self, album: Album) -> None:
        """Upload all tracks for the album.

        Iterates over album.tracks and delegates each upload to TrackUploader.
        Reports per-track progress via the on_progress callback.
        Failed tracks are logged but do NOT trigger a full retry of all tracks.

        Args:
            album: Album instance containing tracks to upload.
        """
        track_uploader = TrackUploader(self.page, self.config, self.resolver)
        failed_tracks = []
        succeeded = 0

        for index, track in enumerate(album.tracks):
            # Report per-track progress
            self._progress.current_step = (
                f"Upload tracks — track {index + 1}/{len(album.tracks)}: {track.title}"
            )
            self._report_progress()
            self._log(f"Uploading track {index + 1}/{len(album.tracks)}: {track.title}")

            success = track_uploader.upload_track(track, index)

            if success:
                self._log(f"Track {index + 1} ({track.title}) uploaded successfully.")
                succeeded += 1
            else:
                self._log(f"Track {index + 1} ({track.title}) failed to upload.")
                failed_tracks.append(track.title)
                # Record the issue but continue with next track
                if self._reporter:
                    self._reporter.record_issue(
                        severity="warning",
                        category="interaction_failed",
                        step=f"Upload track {index + 1}",
                        description=f"Track '{track.title}' failed to upload",
                        suggestion="Check if the file exists and is a valid audio format.",
                    )

        self._log(f"Track upload complete: {succeeded}/{len(album.tracks)} succeeded.")
        
        if failed_tracks and succeeded == 0:
            # Only raise if ALL tracks failed — something is fundamentally wrong
            raise RuntimeError(
                f"All {len(failed_tracks)} tracks failed to upload. "
                f"Check file paths and DistroKid page state."
            )

    def _fill_apple_music_credits(self) -> None:
        """Fill Apple Music performer credits.

        The credits section uses custom searchable dropdowns (dk-searchable-select).
        We need to:
        1. Expand the section ("Add credits for each song on this release")
        2. Click the combobox, type to search, select the option
        3. Fill the name input (id: track-1-performer-1-name)
        4. Click "Copy this performer to all tracks" + confirm
        """
        performers = self.config.apple_music_performers
        if not performers:
            self._log("No Apple Music performer credits configured, skipping.")
            return

        self._log(f"Filling Apple Music performer credits...")
        
        entry = performers[0]
        role = entry.get("role", "")
        name = entry.get("name", "")
        self._log(f"  Performer: {role} — {name}")

        # Expand the Apple Music credits section
        try:
            expand_btn = self.page.get_by_text("Add credits for each song", exact=False)
            if expand_btn.count() > 0:
                expand_btn.first.dispatch_event("click")
                self._log("  Expanded Apple Music credits section.")
                time.sleep(1)
        except Exception:
            pass

        # Fill performer role using the searchable combobox
        # The performer combobox is aria-controls="dk-ss-1-listbox"
        try:
            performer_combobox = self.page.locator("input[aria-controls='dk-ss-1-listbox']")
            if performer_combobox.count() > 0:
                performer_combobox.first.click()
                time.sleep(0.5)
                performer_combobox.first.fill(role)
                time.sleep(0.5)
                # Click the option that EXACTLY matches the role text
                options = self.page.locator("#dk-ss-1-listbox [role='option']")
                matched = False
                for i in range(options.count()):
                    opt_text = options.nth(i).text_content().strip()
                    if opt_text.lower() == role.lower():
                        options.nth(i).click()
                        matched = True
                        self._log(f"  Selected performer role (exact match): {role}")
                        break
                if not matched and options.count() > 0:
                    options.first.click()
                    self._log(f"  Selected first performer role option (no exact match for '{role}').")
                time.sleep(0.3)
            else:
                self._log("  Performer combobox not found, trying JS fallback.")
        except Exception as e:
            self._log(f"  Could not select performer role via combobox: {e}")

        # Fill performer name using the known ID
        try:
            name_input = self.page.locator("#track-1-performer-1-name")
            if name_input.count() > 0:
                name_input.fill(name)
                self._log(f"  Filled performer name: {name}")
            else:
                # Fallback
                name_input = self.page.locator("input.performer-name").first
                name_input.fill(name)
                self._log(f"  Filled performer name (fallback): {name}")
        except Exception as e:
            self._log(f"  Could not fill performer name: {e}")

        # Click "Copy this performer to all tracks on this album"
        time.sleep(0.5)
        try:
            copy_btn = self.page.get_by_text("Copy this performer to all tracks", exact=False)
            if copy_btn.count() > 0:
                copy_btn.first.dispatch_event("click")
                self._log(f"  Clicked 'Copy this performer to all tracks'.")
                time.sleep(1)
                self._click_swal_confirm()
        except Exception as e:
            self._log(f"  Could not click copy performer: {e}")

    def _fill_producer_credits(self) -> None:
        """Fill producer credits in the Apple Music section.

        Similar to performer — uses dk-searchable-select combobox.
        Producer combobox is aria-controls="dk-ss-2-listbox".
        Name input id: track-1-producer-1-name.
        """
        credits = self.config.producer_credits
        if not credits:
            self._log("No producer credits configured, skipping.")
            return

        self._log(f"Filling producer credits...")
        
        entry = credits[0]
        role = entry.get("role", "")
        name = entry.get("name", "")
        self._log(f"  Producer: {role} — {name}")

        # Fill producer role using the searchable combobox
        try:
            producer_combobox = self.page.locator("input[aria-controls='dk-ss-2-listbox']")
            if producer_combobox.count() > 0:
                producer_combobox.first.click()
                time.sleep(0.5)
                producer_combobox.first.fill(role)
                time.sleep(0.5)
                # Click the option that EXACTLY matches the role text
                options = self.page.locator("#dk-ss-2-listbox [role='option']")
                matched = False
                for i in range(options.count()):
                    opt_text = options.nth(i).text_content().strip()
                    if opt_text.lower() == role.lower():
                        options.nth(i).click()
                        matched = True
                        self._log(f"  Selected producer role (exact match): {role}")
                        break
                if not matched and options.count() > 0:
                    options.first.click()
                    self._log(f"  Selected first producer role option (no exact match for '{role}').")
                time.sleep(0.3)
            else:
                self._log("  Producer combobox not found.")
        except Exception as e:
            self._log(f"  Could not select producer role: {e}")

        # Fill producer name using the known ID
        try:
            name_input = self.page.locator("#track-1-producer-1-name")
            if name_input.count() > 0:
                name_input.fill(name)
                self._log(f"  Filled producer name: {name}")
            else:
                name_input = self.page.locator("input.producer-name").first
                name_input.fill(name)
                self._log(f"  Filled producer name (fallback): {name}")
        except Exception as e:
            self._log(f"  Could not fill producer name: {e}")

        # Click "Copy this producer to all tracks on this album"
        time.sleep(0.5)
        try:
            copy_btn = self.page.get_by_text("Copy this producer to all tracks", exact=False)
            if copy_btn.count() > 0:
                copy_btn.first.dispatch_event("click")
                self._log(f"  Clicked 'Copy this producer to all tracks'.")
                time.sleep(1)
                self._click_swal_confirm()
        except Exception as e:
            self._log(f"  Could not click copy producer: {e}")

    def _handle_extras_section(self) -> None:
        """Handle the Extras (optional) section by leaving all checkboxes unchecked.

        Waits for the "Extras" section to appear on the page, then explicitly
        does not interact with any optional checkboxes — they remain unchecked.
        """
        self._log("Handling extras section — leaving all optional checkboxes unchecked.")

        try:
            self.resolver.wait_for_section("Extras")
            self._log("Extras section visible. No optional checkboxes will be checked.")
        except ElementNotFoundError:
            # The extras section may not appear on all form variants — safe to skip
            self._log("Extras section not found on page, skipping.")

    def _handle_mandatory_checkboxes(self) -> None:
        """Check all mandatory checkboxes (class='areyousure') at the bottom of the form.

        DistroKid has a section "Important checkboxes (mandatory)" with checkboxes
        that all have class 'areyousure'. We check all visible ones via JavaScript.
        """
        self._log("Handling mandatory checkboxes...")

        # Check all checkboxes with class 'areyousure' using JavaScript
        checked_count = self.page.evaluate("""
            (() => {
                var checked = 0;
                var checkboxes = document.querySelectorAll('input.areyousure');
                for (var i = 0; i < checkboxes.length; i++) {
                    var cb = checkboxes[i];
                    // Only check visible ones (some are display:none for conditional checkboxes)
                    var parent = cb.closest('.checkbox-grid-cols');
                    if (parent && parent.style.display === 'none') continue;
                    if (!cb.checked) {
                        cb.checked = true;
                        cb.dispatchEvent(new Event('change', {bubbles: true}));
                        checked++;
                    }
                }
                return checked;
            })()
        """)
        
        self._log(f"  Checked {checked_count} mandatory checkbox(es).")

    # --- Retry and utility methods ---

    def _with_retry(self, action_name: str, action_fn: Callable[[], None]) -> None:
        """Wrap an action with retry logic using exponential backoff.

        Retries up to config.retry_count times with delays of 2s, 4s, 8s, etc.
        Re-checks page state before each retry. Records issues to the report.

        Args:
            action_name: Human-readable name of the action (for logging).
            action_fn: Callable to execute (and retry on failure).

        Raises:
            SessionExpiredError: If the page redirects to login.
            PageLoadError: If the page fails to load.
            Exception: The last exception if all retries are exhausted.
        """
        last_exception = None
        max_attempts = self.config.retry_count + 1  # initial + retries

        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    # Exponential backoff: 2s, 4s, 8s, ...
                    delay = 2 ** attempt
                    self._log(
                        f"Retry {attempt}/{self.config.retry_count} for '{action_name}' "
                        f"after {delay}s..."
                    )
                    time.sleep(delay)
                    # Re-check page state before retry
                    self._check_page_state()

                action_fn()
                return  # Success

            except (SessionExpiredError, PageLoadError):
                # These are unrecoverable — re-raise immediately
                raise

            except ElementNotFoundError as e:
                last_exception = e
                self._log(
                    f"Attempt {attempt + 1}/{max_attempts} for '{action_name}' "
                    f"failed: {e}"
                )
                # Record element resolution failure
                if self._reporter and attempt == max_attempts - 1:
                    self._reporter.record_issue(
                        severity="error",
                        category="element_not_found",
                        step=action_name,
                        description=str(e),
                        element=e.description,
                        strategies_tried=e.strategies_attempted,
                        page_url=e.page_url,
                        suggestion=f"Element '{e.description}' not found. DistroKid may have changed this section's layout.",
                    )

            except Exception as e:
                last_exception = e
                self._log(
                    f"Attempt {attempt + 1}/{max_attempts} for '{action_name}' "
                    f"failed: {e}"
                )
                # Record interaction failure
                if self._reporter and attempt == max_attempts - 1:
                    self._reporter.record_issue(
                        severity="error",
                        category="interaction_failed",
                        step=action_name,
                        description=str(e),
                        page_url=self.page.url if self.page else "",
                        suggestion=f"Interaction with form element failed at step '{action_name}'. Check if element is covered or page changed.",
                    )

        # All retries exhausted — this becomes a blocker
        self._log(
            f"All {max_attempts} attempts failed for '{action_name}'. "
            f"Last error: {last_exception}"
        )
        raise last_exception

    def _check_page_state(self) -> None:
        """Detect unexpected page states.

        Raises:
            SessionExpiredError: If URL contains 'login' or 'signin'.
            PageLoadError: If the page is in an unexpected state.
        """
        current_url = self.page.url.lower()
        if "login" in current_url or "signin" in current_url:
            raise SessionExpiredError(url=self.page.url)

    def _run_section(self, step_name: str, action_fn: Callable[[], None]) -> None:
        """Run a section with retry logic and progress reporting.

        Args:
            step_name: Human-readable section name.
            action_fn: The section method to execute.
        """
        self._progress.current_step = step_name
        self._report_progress()

        self._with_retry(step_name, action_fn)

        self._progress.completed_steps += 1
        self._report_progress()

    def _log(self, message: str) -> None:
        """Log a message via the on_log callback and module logger."""
        logger.info(message)
        self._on_log(message)

    def _report_progress(self) -> None:
        """Report current progress via the on_progress callback."""
        self._on_progress(self._progress)

    def _click_swal_confirm(self) -> None:
        """Click SweetAlert2 confirmation buttons until no more appear.
        
        DistroKid shows multiple SweetAlert2 popups in sequence:
        1. "Copy producer?" / "Copy performer?" → "Do it" button
        2. "Done! Happy to save you some time" → "OK" button
        Both use button.swal2-confirm class.
        """
        for _ in range(3):  # Handle up to 3 sequential popups
            try:
                do_it_btn = self.page.locator("button.swal2-confirm")
                if do_it_btn.count() > 0 and do_it_btn.first.is_visible(timeout=3000):
                    do_it_btn.first.click()
                    self._log("  Clicked SweetAlert2 confirm button.")
                    time.sleep(1)
                else:
                    break
            except Exception:
                break
