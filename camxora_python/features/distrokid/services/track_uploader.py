"""
Track Uploader Module

Handles per-track audio file upload and metadata entry on the DistroKid form.
Each track goes through a series of questions (featured artist, version info,
Dolby Atmos, songwriter, explicit lyrics, etc.) that are answered using
configured defaults from UploadFormConfig.
"""

import logging
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from features.distrokid.services.element_resolver import ElementResolver, ElementNotFoundError
from features.distrokid.lib.distrokid_settings import UploadFormConfig
from features.distrokid.models.distrokid_models import Track

logger = logging.getLogger(__name__)


class TrackUploader:
    """Handles per-track upload and metadata entry on the DistroKid form.

    For each track, this class:
    1. Uploads the Suno-downloaded WAV (MP3 / local convert are not allowed)
    2. Sets the track name
    3. Answers all per-track questionnaire fields using config defaults
    """

    def __init__(self, page: Page, config: UploadFormConfig, resolver: ElementResolver):
        """
        Initialize TrackUploader.

        Args:
            page: Playwright Page instance for browser interaction.
            config: UploadFormConfig with per-track default values.
            resolver: ElementResolver instance for finding form elements.
        """
        self.page = page
        self.config = config
        self.resolver = resolver

    def upload_track(self, track: Track, track_index: int) -> bool:
        """Upload a single track and fill its per-track metadata.

        Uploads the audio file and answers all per-track questions in order.
        Requires ``track.wav_path`` to exist on disk (Suno WAV only).

        Args:
            track: Track instance with file paths and title.
            track_index: Zero-based index of the track in the album.

        Returns:
            True on success, False on failure.
        """
        try:
            logger.info(f"Uploading track {track_index + 1}: {track.title}")
            if not track.wav_path or not track.wav_path.exists():
                raise FileNotFoundError(
                    f"Suno WAV missing for track '{track.title}' — DistroKid upload requires .wav"
                )

            # Upload the audio file
            self._upload_audio_file(track, track_index)

            # Fill per-track metadata
            self._set_track_name(track.title, track_index)
            self._answer_featured_artist()
            self._answer_version_info()
            self._answer_dolby_atmos()
            self._answer_songwriter_question()
            self._fill_songwriter_details(track_index)
            self._answer_explicit_lyrics()
            self._answer_radio_edit()
            self._answer_instrumental()
            self._answer_ai_generated()
            self._set_preview_clip()

            logger.info(f"Track {track_index + 1} ({track.title}) uploaded successfully.")
            return True

        except ElementNotFoundError as e:
            logger.error(
                f"Track {track_index + 1} ({track.title}) failed — "
                f"element not found: {e}"
            )
            return False

        except Exception as e:
            logger.error(
                f"Track {track_index + 1} ({track.title}) failed — "
                f"unexpected error: {type(e).__name__}: {e}"
            )
            return False

    def _upload_audio_file(self, track: Track, track_index: int) -> None:
        """Upload the track's audio file.

        Handles:
        - Already uploaded tracks (skip)
        - Previously uploaded but stuck tracks (clear and re-upload)
        - Normal fresh uploads

        Args:
            track: Track instance with path and wav_path fields.
            track_index: Zero-based index of the track.
        """
        import time
        
        track_num = track_index + 1
        
        # Check if already uploaded (title field has content)
        already_uploaded = self.page.evaluate(f"""
            (() => {{
                var titleInput = document.querySelector('input.uploadFileTitle.track_{track_num}');
                if (titleInput && titleInput.value && titleInput.value.trim().length > 0) {{
                    return true;
                }}
                return false;
            }})()
        """)
        
        if already_uploaded:
            logger.info(f"  Track {track_num} already uploaded, skipping.")
            return
        
        # Check if track has a "stuck" previous upload (file input hidden, remove button visible)
        # DistroKid may show a remove/X button for previously uploaded tracks
        stuck_track = self.page.evaluate(f"""
            (() => {{
                var fileInput = document.getElementById('js-track-upload-{track_num}');
                // If file input exists but is hidden (display:none or visibility:hidden)
                if (fileInput) {{
                    var style = window.getComputedStyle(fileInput);
                    if (style.display === 'none' || style.visibility === 'hidden' || fileInput.offsetParent === null) {{
                        return 'hidden';
                    }}
                    return 'visible';
                }}
                return 'not_found';
            }})()
        """)
        logger.info(f"  [DEBUG] Track {track_num} file input state: {stuck_track}")
        
        # If the file input is hidden, try to find and click a remove/clear button
        if stuck_track == 'hidden':
            logger.info(f"  Track {track_num} file input is hidden — attempting to clear previous upload.")
            try:
                # Look for remove/X button for this track
                cleared = self.page.evaluate(f"""
                    (() => {{
                        // Look for remove buttons near this track's upload area
                        var removeButtons = document.querySelectorAll('.remove-track, .track-remove, [class*="remove"], [class*="delete"], [title*="Remove"]');
                        for (var i = 0; i < removeButtons.length; i++) {{
                            var btn = removeButtons[i];
                            var parent = btn.closest('[class*="track_{track_num}"], [class*="trackupload_{track_num}"]');
                            if (parent) {{
                                btn.click();
                                return true;
                            }}
                        }}
                        // Alternative: try to reset the file input
                        var fileInput = document.getElementById('js-track-upload-{track_num}');
                        if (fileInput) {{
                            fileInput.value = '';
                            fileInput.style.display = '';
                            fileInput.style.visibility = '';
                            return true;
                        }}
                        return false;
                    }})()
                """)
                if cleared:
                    logger.info(f"  Cleared previous track {track_num} upload.")
                    time.sleep(1)
            except Exception as e:
                logger.info(f"  Could not clear track {track_num}: {e}")
        
        # Suno WAV only — never upload MP3 or locally converted audio.
        if not track.wav_path or not track.wav_path.exists():
            raise FileNotFoundError(
                f"Suno WAV missing for track '{track.title}' (index {track_index})"
            )
        if track.wav_path.suffix.lower() != ".wav":
            raise ValueError(
                f"DistroKid upload requires .wav, got {track.wav_path.suffix}: {track.wav_path.name}"
            )
        upload_path = track.wav_path

        logger.info(f"  Uploading file: {upload_path.name}")

        # Find the file input
        selector = f"#js-track-upload-{track_num}"
        file_input = self.page.locator(selector)
        
        if file_input.count() == 0:
            fallback = f"input.trackupload_{track_num}"
            file_input = self.page.locator(fallback)
            
            if file_input.count() == 0:
                # For singles, try generic audio file input
                generic = "input[type='file'][accept*='audio']"
                file_input = self.page.locator(generic)
                
                if file_input.count() == 0:
                    try:
                        file_input = self.page.locator(selector)
                        file_input.wait_for(state="attached", timeout=15000)
                    except Exception as e:
                        logger.error(f"  Track {track_num} file input not found: {e}")
                        raise
        
        # Upload the file
        file_input.set_input_files(str(upload_path))
        logger.info(f"  File set on input: {upload_path.name}")
        
        # Manually trigger the onchange event to ensure DistroKid processes it
        self.page.evaluate(f"""
            (() => {{
                var input = document.getElementById('js-track-upload-{track_num}') ||
                            document.querySelector('input.trackupload_{track_num}') ||
                            document.querySelector("input[type='file'][accept*='audio']");
                if (input) {{
                    var event = new Event('change', {{ bubbles: true }});
                    input.dispatchEvent(event);
                }}
            }})()
        """)
        logger.info(f"  Dispatched change event on track {track_num} input.")
        
        # Wait for the upload to be processed — DistroKid's newReleaseChangedAudioFile()
        # needs time to process the file. Wait for the title input to appear as confirmation.
        title_selector = f"input.uploadFileTitle.track_{track_num}"
        try:
            title_input = self.page.locator(title_selector)
            title_input.wait_for(state="visible", timeout=30000)
            logger.info(f"  Track {track_num} title input appeared — upload accepted.")
        except Exception:
            # Title input didn't appear in 30s — the upload might have failed
            logger.warning(f"  Track {track_num} title input didn't appear after 30s.")
            # Still wait a bit in case it's just slow
            time.sleep(3)
        
        # Dismiss any modal that appeared
        try:
            cancel_btn = self.page.get_by_text("Cancel", exact=True)
            if cancel_btn.count() > 0 and cancel_btn.first.is_visible(timeout=1000):
                cancel_btn.first.click()
                logger.info("  Dismissed modal after track upload.")
                time.sleep(0.5)
        except Exception:
            pass

    def _set_track_name(self, title: str, track_index: int) -> None:
        """Fill the track title field with the given title.

        DistroKid uses: input.uploadFileTitle.track_N (1-based)
        with placeholder="Track N title"

        Args:
            title: The track title to enter.
            track_index: Zero-based track index.
        """
        import time
        track_num = track_index + 1
        logger.debug(f"Setting track {track_num} name: {title}")

        # Use the known DistroKid selector: input.uploadFileTitle.track_N
        selector = f"input.uploadFileTitle.track_{track_num}"
        title_input = self.page.locator(selector)
        
        # Wait for it to appear (may load after file upload)
        try:
            title_input.wait_for(state="visible", timeout=10000)
            title_input.fill(title)
            logger.debug(f"  Set track {track_num} title via class selector.")
        except Exception:
            # Fallback: try by placeholder
            fallback = self.page.locator(f"input[placeholder='Track {track_num} title']")
            try:
                fallback.wait_for(state="visible", timeout=5000)
                fallback.fill(title)
                logger.debug(f"  Set track {track_num} title via placeholder.")
            except Exception:
                # Last fallback: find by tracknum attribute
                attr_selector = f"input[tracknum='{track_num}']"
                attr_input = self.page.locator(attr_selector)
                if attr_input.count() > 0:
                    attr_input.fill(title)
                else:
                    logger.warning(f"  Could not find title input for track {track_num}")

    def _answer_featured_artist(self) -> None:
        """Select 'No, don't show any other artists' for the featured artist question."""
        logger.debug("Answering featured artist: No")

        radio = self.resolver.resolve_radio_option(
            question_text="featured artist",
            option_text="No, don't show any other artists",
        )
        radio.dispatch_event("click")

    def _answer_version_info(self) -> None:
        """Select 'No, this is the normal version' for the version info question."""
        logger.debug("Answering version info: Normal version")

        radio = self.resolver.resolve_radio_option(
            question_text="version",
            option_text="No, this is the normal version",
        )
        radio.dispatch_event("click")

    def _answer_dolby_atmos(self) -> None:
        """Select 'No' for the Dolby Atmos / spatial audio question."""
        logger.debug("Answering Dolby Atmos: No")

        radio = self.resolver.resolve_radio_option(
            question_text="Dolby Atmos",
            option_text="No",
        )
        radio.dispatch_event("click")

    def _answer_songwriter_question(self) -> None:
        """Select 'I wrote this song' for the songwriter/cover song question."""
        logger.debug("Answering songwriter question: I wrote this song")

        radio = self.resolver.resolve_radio_option(
            question_text="songwriter",
            option_text="I wrote this song",
        )
        radio.dispatch_event("click")

    def _fill_songwriter_details(self, track_index: int) -> None:
        """Fill songwriter role, first name, and last name from config.

        On track 1: fills the details and clicks "Copy these songwriters to all tracks".
        On subsequent tracks: skips (already copied from track 1).
        """
        import time
        
        # Only fill on the first track — use "Copy to all tracks" for the rest
        if track_index > 0:
            logger.debug(f"  Track {track_index + 1}: songwriter already copied from track 1, skipping.")
            return
        
        logger.debug(
            f"Filling songwriter details: {self.config.songwriter_role} — "
            f"{self.config.songwriter_first_name} {self.config.songwriter_last_name}"
        )

        # Select songwriter role — uses class 'songwriter_real_name_role' with tracknum=1
        # Note: DistroKid uses "Music and lyrics" (lowercase L) not "Music and Lyrics"
        role_dropdown = self.page.locator("select.songwriter_real_name_role[tracknum='1']")
        if role_dropdown.count() == 0:
            role_dropdown = self.page.locator("select.songwriter_real_name_role").first
        
        # Use JS to select by case-insensitive label match
        role_value = self.config.songwriter_role
        self.page.evaluate(f"""
            (() => {{
                var select = document.querySelector("select.songwriter_real_name_role[tracknum='1']") || 
                             document.querySelector("select.songwriter_real_name_role");
                if (select) {{
                    var target = '{role_value}'.toLowerCase();
                    for (var i = 0; i < select.options.length; i++) {{
                        if (select.options[i].text.toLowerCase() === target) {{
                            select.selectedIndex = i;
                            select.dispatchEvent(new Event('change'));
                            break;
                        }}
                    }}
                }}
            }})()
        """)

        # Fill first name — uses class 'songwriter_real_name_first' with placeholder "First name"
        first_input = self.page.locator("input.songwriter_real_name_first[tracknum='1']")
        if first_input.count() == 0:
            first_input = self.page.locator("input[placeholder='First name']").first
        first_input.fill(self.config.songwriter_first_name)

        # Fill last name — uses class 'songwriter_real_name_last' with placeholder "Last name"
        last_input = self.page.locator("input.songwriter_real_name_last[tracknum='1']")
        if last_input.count() == 0:
            last_input = self.page.locator("input[placeholder='Last name']").first
        last_input.fill(self.config.songwriter_last_name)

        # Click "Copy these songwriters to all tracks on this album"
        time.sleep(0.5)
        try:
            copy_btn = self.page.get_by_text("Copy these songwriters to all tracks", exact=False)
            if copy_btn.count() > 0:
                copy_btn.first.dispatch_event("click")
                logger.info("  Clicked 'Copy these songwriters to all tracks'.")
                time.sleep(1)
                # Confirm the SweetAlert2 "Do it" popup + "Done/OK" popup
                try:
                    for _ in range(3):
                        do_it_btn = self.page.locator("button.swal2-confirm")
                        if do_it_btn.count() > 0 and do_it_btn.first.is_visible(timeout=3000):
                            do_it_btn.first.click()
                            logger.info("  Clicked SweetAlert2 confirm button.")
                            import time as t
                            t.sleep(1)
                        else:
                            break
                except Exception:
                    pass
            else:
                logger.debug("  'Copy to all tracks' button not found, will fill per-track.")
        except Exception as e:
            logger.debug(f"  Could not click 'Copy to all tracks': {e}")

    def _answer_explicit_lyrics(self) -> None:
        """Answer the explicit lyrics question using config value."""
        answer = "Yes" if self.config.explicit_lyrics else "No"
        logger.debug(f"Answering explicit lyrics: {answer}")

        radio = self.resolver.resolve_radio_option(
            question_text="explicit",
            option_text=answer,
        )
        radio.dispatch_event("click")

    def _answer_radio_edit(self) -> None:
        """Answer the radio edit question using config value."""
        answer = "Yes" if self.config.radio_edit else "No"
        logger.debug(f"Answering radio edit: {answer}")

        radio = self.resolver.resolve_radio_option(
            question_text="radio edit",
            option_text=answer,
        )
        radio.dispatch_event("click")

    def _answer_instrumental(self) -> None:
        """Answer the instrumental question using config value."""
        answer = "Yes" if self.config.instrumental else "No"
        logger.debug(f"Answering instrumental: {answer}")

        radio = self.resolver.resolve_radio_option(
            question_text="instrumental",
            option_text=answer,
        )
        radio.dispatch_event("click")

    def _answer_ai_generated(self) -> None:
        """Answer the AI-generated content question using config value."""
        answer = "Yes" if self.config.ai_generated else "No"
        logger.debug(f"Answering AI-generated: {answer}")

        radio = self.resolver.resolve_radio_option(
            question_text="AI",
            option_text=answer,
        )
        radio.dispatch_event("click")

    def _set_preview_clip(self) -> None:
        """Select the configured preview clip preference."""
        preference = self.config.preview_clip_preference
        logger.debug(f"Setting preview clip preference: {preference}")

        radio = self.resolver.resolve_radio_option(
            question_text="preview",
            option_text=preference,
        )
        radio.dispatch_event("click")
