"""Onboarding controller — orchestrates email verification + channel wizard.

Handles API calls for:
- Sending/verifying email codes
- Generating channel names, logos, covers, descriptions for both channels
- Creating both channel profiles at once
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

import httpx
from PyQt6.QtCore import Qt

from python_app.views.onboarding_view import ConfirmCodePage, ChannelWizardPage, SlideStackedWidget

logger = logging.getLogger(__name__)

_API = "http://localhost:8000/api/v1"


class OnboardingController:
    """Manages the onboarding flow: confirm code → channel wizard → dashboard."""

    _STEP_TITLES = [
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
    ]

    def __init__(
        self,
        login_view,
        token_store,
        on_complete: Callable[[], None],
        bus=None,
    ):
        self._login_view = login_view
        self._token_store = token_store
        self._on_complete = on_complete
        self._bus = bus
        self._email = ""
        self._access_token = ""

        # Create onboarding pages
        self._confirm_page = ConfirmCodePage()
        self._wizard_page = ChannelWizardPage()

        # Create slide stack for onboarding
        self._onboarding_stack = SlideStackedWidget()
        self._onboarding_stack.addWidget(self._confirm_page)
        self._onboarding_stack.addWidget(self._wizard_page)

        # Wire signals
        self._confirm_page.verified.connect(self._on_code_verify)
        self._confirm_page._resend_callback = self._send_verification_code
        self._wizard_page.completed.connect(self._on_wizard_complete)
        self._wizard_page.step_changed.connect(self._on_wizard_step_changed)

        # Wire wizard callbacks
        self._wizard_page._generate_names_callback = self._api_generate_names
        self._wizard_page._generate_logo_callback = self._api_generate_logo
        self._wizard_page._generate_covers_callback = self._api_generate_covers
        self._wizard_page._generate_description_callback = self._api_generate_description
        self._wizard_page._create_profiles_callback = self._api_create_profiles

    def start(self, email: str, access_token: str = "", skip_verification: bool = False) -> None:
        """Show onboarding within the login view."""
        self._email = email
        self._access_token = access_token

        # Enter onboarding mode on the login view
        self._login_view.enter_onboarding_mode()

        # Insert onboarding stack into the column layout
        form_stack = self._login_view._form_stack
        column_layout = self._login_view._column.layout()
        form_stack.hide()
        column_layout.addWidget(self._onboarding_stack)

        # Reset and start
        self._confirm_page.reset()
        self._wizard_page.reset()

        if skip_verification:
            # Email already confirmed — go straight to wizard
            self._onboarding_stack.setCurrentIndex(1)
            self._update_title(self._wizard_page._STEP_TITLES[0])
            self._load_genres()
        else:
            self._onboarding_stack.setCurrentIndex(0)
            self._send_verification_code()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._access_token:
            h["Authorization"] = f"Bearer {self._access_token}"
        return h

    # ────────────────────────────────────────────────────────────
    # Email verification
    # ────────────────────────────────────────────────────────────

    def _send_verification_code(self) -> None:
        def work():
            try:
                resp = httpx.post(
                    f"{_API}/auth/send-verification",
                    json={"email": self._email},
                    timeout=15.0,
                )
                logger.info("Send verification: %s", resp.status_code)
            except Exception as exc:
                logger.error("Failed to send verification: %s", exc)

        threading.Thread(target=work, daemon=True).start()

    def _on_code_verify(self) -> None:
        code = self._confirm_page._code_input.text().strip()

        def work():
            try:
                resp = httpx.post(
                    f"{_API}/auth/verify-email",
                    json={"email": self._email, "code": code},
                    timeout=15.0,
                )
                data = resp.json()

                def apply():
                    if resp.status_code == 200 and data.get("is_verified"):
                        # Slide to wizard page
                        self._onboarding_stack.slide_to(1, "right")
                        self._load_genres()
                    else:
                        msg = data.get("message", "Invalid code")
                        self._confirm_page.show_error(msg)

                if self._bus:
                    self._bus.ui_invoke.emit(apply)
                else:
                    apply()
            except Exception as exc:
                logger.error("Verify failed: %s", exc)

        threading.Thread(target=work, daemon=True).start()

    def _load_genres(self) -> None:
        def work():
            try:
                resp = httpx.get(
                    f"{_API}/prompts/descriptions/public",
                    headers=self._headers(),
                    timeout=15.0,
                )
                genres = resp.json() if resp.status_code == 200 else []

                def apply():
                    self._wizard_page.load_genres(genres)

                if self._bus:
                    self._bus.ui_invoke.emit(apply)
                else:
                    apply()
            except Exception as exc:
                logger.error("Failed to load genres: %s", exc)

        threading.Thread(target=work, daemon=True).start()

    def _on_wizard_step_changed(self, step: int) -> None:
        title = ChannelWizardPage._STEP_TITLES[step] if step < len(ChannelWizardPage._STEP_TITLES) else "Set up your channels"
        self._update_title(title)

    def _update_title(self, text: str) -> None:
        title_widget = getattr(self._login_view, '_title', None)
        if title_widget is not None:
            title_widget.setText(text)
            title_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _on_wizard_complete(self) -> None:
        # Clean up: remove onboarding stack, restore login view
        self._onboarding_stack.hide()
        self._login_view.exit_onboarding_mode()
        self._on_complete()

    # ────────────────────────────────────────────────────────────
    # Wizard API calls
    # ────────────────────────────────────────────────────────────

    def _api_generate_names(self, genre: str, role: str) -> None:
        """Generate channel names via a single API call.

        When role is 'both', requests 20 names and splits them 10/10 between
        primary and secondary. When 'primary' or 'secondary', requests 10.
        """
        # Get custom prompt if provided (from pending prompt or input field)
        custom_prompt = ""
        if hasattr(self, '_wizard_page') and hasattr(self._wizard_page, '_pending_custom_prompt'):
            custom_prompt = getattr(self._wizard_page, '_pending_custom_prompt', '')
            self._wizard_page._pending_custom_prompt = ''
        if not custom_prompt and hasattr(self, '_wizard_page') and hasattr(self._wizard_page, '_custom_prompt_input'):
            custom_prompt = self._wizard_page._custom_prompt_input.text().strip()

        description = custom_prompt if custom_prompt else ""
        match_key = getattr(self._wizard_page, "_genre_match_key", "") or genre
        count = 20 if role == "both" else 10

        def work():
            try:
                resp = httpx.post(
                    f"{_API}/channel-setup/generate-names",
                    json={
                        "genre": genre,
                        "role": role,
                        "description": description,
                        "match_key": match_key,
                        "count": count,
                    },
                    headers=self._headers(),
                    timeout=90.0,
                )
                data = resp.json()
                names = data.get("names", [])

                def apply():
                    if resp.status_code == 200 and names:
                        if role == "both":
                            # Split: first 10 → primary, last 10 → secondary
                            mid = len(names) // 2
                            self._wizard_page.set_names(names[:mid], "primary")
                            self._wizard_page.set_names(names[mid:], "secondary")
                        else:
                            self._wizard_page.set_names(names, role)
                    else:
                        msg = ""
                        try:
                            msg = (data.get("error") or {}).get("message", "")
                        except Exception:
                            msg = ""
                        if not msg:
                            msg = "No names returned. Check Channel Prompts in admin portal."
                        if role == "both":
                            self._wizard_page.set_names_error(msg, "primary")
                            self._wizard_page.set_names_error(msg, "secondary")
                        else:
                            self._wizard_page.set_names_error(msg, role)

                if self._bus:
                    self._bus.ui_invoke.emit(apply)
                else:
                    apply()
            except Exception as exc:
                logger.error("Generate names (%s) failed: %s", role, exc)

                def fail():
                    err = "Couldn't reach the server. Is the API running on :8000?"
                    if role == "both":
                        self._wizard_page.set_names_error(err, "primary")
                        self._wizard_page.set_names_error(err, "secondary")
                    else:
                        self._wizard_page.set_names_error(err, role)

                if self._bus:
                    self._bus.ui_invoke.emit(fail)
                else:
                    fail()

        threading.Thread(target=work, daemon=True).start()

    def _api_generate_logo(self, channel_name: str, genre: str, role: str) -> None:
        match_key = getattr(self._wizard_page, "_genre_match_key", "") or genre

        def work():
            try:
                resp = httpx.post(
                    f"{_API}/channel-setup/generate-logo",
                    json={"channel_name": channel_name, "genre": genre, "role": role, "match_key": match_key},
                    headers=self._headers(),
                    timeout=300.0,
                )
                data = resp.json()
                image_b64 = data.get("image_base64", "")

                def apply():
                    self._wizard_page.set_logo(image_b64, role)

                if self._bus:
                    self._bus.ui_invoke.emit(apply)
                else:
                    apply()
            except Exception as exc:
                logger.error("Generate logo (%s) failed: %s", role, exc)

                def show_retry():
                    self._wizard_page.set_logo_retry(role)

                if self._bus:
                    self._bus.ui_invoke.emit(show_retry)
                else:
                    show_retry()

        threading.Thread(target=work, daemon=True).start()

    def _api_generate_covers(self, channel_name: str, genre: str, role: str) -> None:
        def work():
            try:
                resp = httpx.post(
                    f"{_API}/channel-setup/generate-covers",
                    json={"channel_name": channel_name, "genre": genre, "count": 3, "role": role},
                    headers=self._headers(),
                    timeout=300.0,
                )
                data = resp.json()
                images = data.get("images", [])

                def apply():
                    self._wizard_page.set_covers(images, role)

                if self._bus:
                    self._bus.ui_invoke.emit(apply)
                else:
                    apply()
            except Exception as exc:
                logger.error("Generate covers (%s) failed: %s", role, exc)

                def show_retry():
                    self._wizard_page.set_covers_retry(role)

                if self._bus:
                    self._bus.ui_invoke.emit(show_retry)
                else:
                    show_retry()

        threading.Thread(target=work, daemon=True).start()

    def _api_generate_description(self, channel_name: str, genre: str) -> None:
        def work():
            try:
                resp = httpx.post(
                    f"{_API}/channel-setup/generate-description",
                    json={"channel_name": channel_name, "genre": genre},
                    headers=self._headers(),
                    timeout=120.0,
                )
                data = resp.json()

                def apply():
                    if resp.status_code == 200:
                        self._wizard_page.set_description(
                            data.get("description", ""),
                            data.get("keywords", []),
                            data.get("tags", []),
                        )
                    else:
                        self._wizard_page.set_description_error("Generation failed. Please retry.")

                if self._bus:
                    self._bus.ui_invoke.emit(apply)
                else:
                    apply()
            except Exception as exc:
                logger.error("Generate description failed: %s", exc)

                def show_error():
                    self._wizard_page.set_description_error("Connection timed out. Please retry.")

                if self._bus:
                    self._bus.ui_invoke.emit(show_error)
                else:
                    show_error()

        threading.Thread(target=work, daemon=True).start()

    # ────────────────────────────────────────────────────────────
    # Create both channel profiles
    # ────────────────────────────────────────────────────────────

    def _api_create_profiles(
        self,
        primary_name: str,
        secondary_name: str,
        genre: str,
        primary_logo_b64: str,
        secondary_logo_b64: str,
        description: str,
        keywords: list[str],
        tags: list[str],
    ) -> None:
        match_key = getattr(self._wizard_page, "_genre_match_key", "") or genre
        primary_covers = getattr(self._wizard_page, "_primary_covers_b64s", [])
        secondary_covers = getattr(self._wizard_page, "_secondary_covers_b64s", [])

        def work():
            success_count = 0
            errors = []

            for name, logo_b64, role, covers in [
                (primary_name, primary_logo_b64, "primary", primary_covers),
                (secondary_name, secondary_logo_b64, "secondary", secondary_covers),
            ]:
                try:
                    resp = httpx.post(
                        f"{_API}/channel-setup/create-profile",
                        json={
                            "name": name,
                            "genre": genre,
                            "role": role,
                            "logo_base64": logo_b64 or None,
                            "cover_images": covers,
                            "description": description,
                            "keywords": keywords,
                            "tags": tags,
                            "match_key": match_key,
                        },
                        headers=self._headers(),
                        timeout=90.0,
                    )
                    if resp.status_code in (200, 201):
                        success_count += 1
                        logger.info("Created %s profile: %s", role, resp.status_code)
                    else:
                        errors.append(f"{role}: {resp.status_code}")
                        logger.error("Create %s profile failed: %s", role, resp.text[:200])
                except Exception as exc:
                    errors.append(f"{role}: {exc}")
                    logger.error("Create %s profile failed: %s", role, exc)

            def apply():
                if success_count == 2:
                    # Both profiles created — navigate to dashboard
                    self._wizard_page.on_profiles_created()
                else:
                    # Something failed — allow retry
                    msg = "; ".join(errors) if errors else "Unknown error"
                    self._wizard_page.on_profiles_failed(msg)

            if self._bus:
                self._bus.ui_invoke.emit(apply)
            else:
                apply()

        threading.Thread(target=work, daemon=True).start()
