"""
Element Resolver Module

Finds form elements dynamically using multiple resolution strategies.
Uses text, labels, ARIA attributes, and structural context instead of brittle CSS selectors.
"""

import logging
from typing import Optional

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class ElementNotFoundError(Exception):
    """Raised when an element cannot be found after all resolution strategies are exhausted."""

    def __init__(self, description: str, strategies_attempted: list[str] = None, page_url: str = ""):
        self.description = description
        self.strategies_attempted = strategies_attempted or []
        self.page_url = page_url
        strategies_info = ", ".join(self.strategies_attempted) if self.strategies_attempted else "none"
        message = (
            f"Could not find element: '{description}'. "
            f"Strategies attempted: [{strategies_info}]. "
            f"Page URL: {page_url}"
        )
        super().__init__(message)


class ElementResolver:
    """Finds form elements dynamically using multiple resolution strategies.

    Resolution strategy order:
    1. Exact text match via page.get_by_text(text, exact=True)
    2. Label association via page.get_by_label(label)
    3. ARIA attribute via [aria-label="..."]
    4. Nearby text scan — find text node, traverse to nearest interactive sibling
    5. Fallback CSS selector (legacy support)
    6. Partial text match via page.get_by_text(text, exact=False)
    """

    def __init__(self, page: Page, timeout: int = 30000):
        """
        Initialize ElementResolver.

        Args:
            page: Playwright Page instance to resolve elements on.
            timeout: Default timeout in milliseconds for element resolution.
        """
        self.page = page
        self.timeout = timeout

    def resolve(
        self,
        description: str,
        element_type: str,
        *,
        text: str = None,
        label: str = None,
        aria_label: str = None,
        near_text: str = None,
        fallback_selector: str = None,
    ) -> Locator:
        """Locate a form element using multiple strategies with fallback.

        Tries strategies in order: exact text → label → ARIA → nearby text →
        fallback CSS → partial text. Returns the first locator that matches a
        visible element.

        Args:
            description: Human-readable description of the element being sought.
            element_type: Type of element ("radio", "checkbox", "dropdown",
                          "text_input", "file_input", "button").
            text: Text content to search for (used in exact and partial strategies).
            label: Label text associated with the element.
            aria_label: ARIA label attribute value.
            near_text: Text near the target element for contextual resolution.
            fallback_selector: CSS selector as a last-resort fallback.

        Returns:
            A Playwright Locator pointing to the resolved element.

        Raises:
            ElementNotFoundError: If no strategy can locate the element.
        """
        strategies_attempted = []

        # Strategy 1: Exact text match
        if text:
            strategies_attempted.append("exact_text")
            locator = self._try_exact_text(text, element_type)
            if locator:
                logger.debug(f"Resolved '{description}' via exact text match: '{text}'")
                return locator

        # Strategy 2: Label association
        if label:
            strategies_attempted.append("label")
            locator = self._try_label(label)
            if locator:
                logger.debug(f"Resolved '{description}' via label: '{label}'")
                return locator

        # Strategy 3: ARIA attribute
        if aria_label:
            strategies_attempted.append("aria_label")
            locator = self._try_aria_label(aria_label)
            if locator:
                logger.debug(f"Resolved '{description}' via ARIA label: '{aria_label}'")
                return locator

        # Strategy 4: Nearby text scan
        if near_text:
            strategies_attempted.append("near_text")
            locator = self._try_near_text(near_text, element_type)
            if locator:
                logger.debug(f"Resolved '{description}' via nearby text: '{near_text}'")
                return locator

        # Strategy 5: Fallback CSS selector
        if fallback_selector:
            strategies_attempted.append("fallback_css")
            locator = self._try_css_selector(fallback_selector)
            if locator:
                logger.debug(f"Resolved '{description}' via fallback CSS: '{fallback_selector}'")
                return locator

        # Strategy 6: Partial text match
        if text:
            strategies_attempted.append("partial_text")
            locator = self._try_partial_text(text, element_type)
            if locator:
                logger.debug(f"Resolved '{description}' via partial text match: '{text}'")
                return locator

        # All strategies exhausted
        page_url = self.page.url if self.page else ""
        logger.error(
            f"Element resolution failed for '{description}'. "
            f"Strategies attempted: {strategies_attempted}. URL: {page_url}"
        )
        raise ElementNotFoundError(
            description=description,
            strategies_attempted=strategies_attempted,
            page_url=page_url,
        )

    def resolve_radio_option(self, question_text: str, option_text: str) -> Locator:
        """Find and return a radio button option within a question context.

        Locates the question text on the page, then finds the radio button
        associated with the given option text within that context.

        Args:
            question_text: The text of the question containing the radio group.
            option_text: The text label of the desired radio option.

        Returns:
            A Playwright Locator pointing to the radio input element.

        Raises:
            ElementNotFoundError: If the radio option cannot be found.
        """
        strategies_attempted = []

        # Strategy 1: Find question section, then locate radio by label text within it
        strategies_attempted.append("question_context_label")
        try:
            # Find the section containing the question text
            question_section = self.page.locator(
                f":has-text('{question_text}')"
            ).first
            # Within that section, find the radio option by its label text
            radio = question_section.get_by_label(option_text)
            if radio.count() > 0 and radio.first.is_visible(timeout=2000):
                return radio.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 2: Find label with option text near the question, get associated input
        strategies_attempted.append("option_text_input")
        try:
            # Look for a label containing the option text and get its input
            label_locator = self.page.locator(
                f"label:has-text('{option_text}')"
            )
            if label_locator.count() > 0:
                # Try to find input[type=radio] within the label
                radio = label_locator.first.locator("input[type='radio']")
                if radio.count() > 0:
                    return radio.first
                # Try the 'for' attribute
                for_attr = label_locator.first.get_attribute("for")
                if for_attr:
                    radio = self.page.locator(f"#{for_attr}")
                    if radio.count() > 0:
                        return radio.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 3: Use get_by_role with radio and name
        strategies_attempted.append("role_radio")
        try:
            radio = self.page.get_by_role("radio", name=option_text)
            if radio.count() > 0 and radio.first.is_visible(timeout=2000):
                return radio.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 4: Find text, traverse to nearby radio input
        strategies_attempted.append("nearby_radio_traversal")
        try:
            text_element = self.page.get_by_text(option_text, exact=False)
            if text_element.count() > 0:
                # Look for a radio input as a sibling or within the parent
                parent = text_element.first.locator("..")
                radio = parent.locator("input[type='radio']")
                if radio.count() > 0:
                    return radio.first
        except (PlaywrightTimeoutError, Exception):
            pass

        page_url = self.page.url if self.page else ""
        raise ElementNotFoundError(
            description=f"Radio option '{option_text}' for question '{question_text}'",
            strategies_attempted=strategies_attempted,
            page_url=page_url,
        )

    def resolve_checkbox(self, label_text: str) -> Locator:
        """Find a checkbox by its associated label text.

        Args:
            label_text: The label text associated with the checkbox.

        Returns:
            A Playwright Locator pointing to the checkbox input element.

        Raises:
            ElementNotFoundError: If the checkbox cannot be found.
        """
        strategies_attempted = []

        # Strategy 1: get_by_label
        strategies_attempted.append("label")
        try:
            checkbox = self.page.get_by_label(label_text)
            if checkbox.count() > 0 and checkbox.first.is_visible(timeout=2000):
                return checkbox.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 2: get_by_role with checkbox
        strategies_attempted.append("role_checkbox")
        try:
            checkbox = self.page.get_by_role("checkbox", name=label_text)
            if checkbox.count() > 0 and checkbox.first.is_visible(timeout=2000):
                return checkbox.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 3: Find label element, get associated input
        strategies_attempted.append("label_for_attr")
        try:
            label_locator = self.page.locator(f"label:has-text('{label_text}')")
            if label_locator.count() > 0:
                # Check for input within the label
                checkbox = label_locator.first.locator("input[type='checkbox']")
                if checkbox.count() > 0:
                    return checkbox.first
                # Check for 'for' attribute
                for_attr = label_locator.first.get_attribute("for")
                if for_attr:
                    checkbox = self.page.locator(f"#{for_attr}")
                    if checkbox.count() > 0:
                        return checkbox.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 4: Nearby text traversal
        strategies_attempted.append("near_text_traversal")
        try:
            text_el = self.page.get_by_text(label_text, exact=False)
            if text_el.count() > 0:
                parent = text_el.first.locator("..")
                checkbox = parent.locator("input[type='checkbox']")
                if checkbox.count() > 0:
                    return checkbox.first
        except (PlaywrightTimeoutError, Exception):
            pass

        page_url = self.page.url if self.page else ""
        raise ElementNotFoundError(
            description=f"Checkbox with label '{label_text}'",
            strategies_attempted=strategies_attempted,
            page_url=page_url,
        )

    def resolve_dropdown(self, label_text: str) -> Locator:
        """Find a select/dropdown element by label or nearby text.

        Args:
            label_text: The label text associated with the dropdown.

        Returns:
            A Playwright Locator pointing to the select element.

        Raises:
            ElementNotFoundError: If the dropdown cannot be found.
        """
        strategies_attempted = []

        # Strategy 1: get_by_label for select
        strategies_attempted.append("label")
        try:
            select = self.page.get_by_label(label_text)
            if select.count() > 0:
                # Verify it's actually a select element
                first = select.first
                tag = first.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select" and first.is_visible(timeout=2000):
                    return first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 2: get_by_role combobox
        strategies_attempted.append("role_combobox")
        try:
            select = self.page.get_by_role("combobox", name=label_text)
            if select.count() > 0 and select.first.is_visible(timeout=2000):
                return select.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 3: Find label, get associated select via 'for' attribute
        strategies_attempted.append("label_for_attr")
        try:
            label_locator = self.page.locator(f"label:has-text('{label_text}')")
            if label_locator.count() > 0:
                for_attr = label_locator.first.get_attribute("for")
                if for_attr:
                    select = self.page.locator(f"select#{for_attr}")
                    if select.count() > 0:
                        return select.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 4: Find text, look for nearby select element
        strategies_attempted.append("near_text_select")
        try:
            text_el = self.page.get_by_text(label_text, exact=False)
            if text_el.count() > 0:
                # Check parent for a select
                parent = text_el.first.locator("..")
                select = parent.locator("select")
                if select.count() > 0:
                    return select.first
                # Check grandparent
                grandparent = parent.locator("..")
                select = grandparent.locator("select")
                if select.count() > 0:
                    return select.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 5: ARIA label on select
        strategies_attempted.append("aria_label_select")
        try:
            select = self.page.locator(f"select[aria-label='{label_text}']")
            if select.count() > 0 and select.first.is_visible(timeout=2000):
                return select.first
        except (PlaywrightTimeoutError, Exception):
            pass

        page_url = self.page.url if self.page else ""
        raise ElementNotFoundError(
            description=f"Dropdown with label '{label_text}'",
            strategies_attempted=strategies_attempted,
            page_url=page_url,
        )

    def resolve_file_input(self, accept_type: str = None) -> Locator:
        """Find a file input, optionally filtered by accept attribute.

        Args:
            accept_type: Optional accept attribute filter (e.g., "audio/*", "image/*").
                         If None, returns the first visible file input.

        Returns:
            A Playwright Locator pointing to the file input element.

        Raises:
            ElementNotFoundError: If no matching file input is found.
        """
        strategies_attempted = []

        # Strategy 1: Filter by accept attribute if provided
        if accept_type:
            strategies_attempted.append(f"accept_attr({accept_type})")
            try:
                selector = f"input[type='file'][accept*='{accept_type}']"
                file_input = self.page.locator(selector)
                if file_input.count() > 0:
                    return file_input.first
            except (PlaywrightTimeoutError, Exception):
                pass

        # Strategy 2: Any file input on the page
        strategies_attempted.append("any_file_input")
        try:
            file_input = self.page.locator("input[type='file']")
            if file_input.count() > 0:
                return file_input.first
        except (PlaywrightTimeoutError, Exception):
            pass

        # Strategy 3: Get by role (some pages use different markup)
        strategies_attempted.append("role_file_input")
        try:
            # Some file inputs may not have explicit type but use ARIA
            file_input = self.page.locator("[role='button'][aria-label*='upload']")
            if file_input.count() > 0:
                return file_input.first
        except (PlaywrightTimeoutError, Exception):
            pass

        page_url = self.page.url if self.page else ""
        raise ElementNotFoundError(
            description=f"File input (accept: {accept_type or 'any'})",
            strategies_attempted=strategies_attempted,
            page_url=page_url,
        )

    def wait_for_section(self, section_text: str, timeout: int = None) -> bool:
        """Wait for a page section containing the given text to become visible.

        Args:
            section_text: Text content that identifies the section.
            timeout: Timeout in milliseconds (uses instance default if None).

        Returns:
            True if the section becomes visible within the timeout.

        Raises:
            ElementNotFoundError: If the section does not appear within the timeout.
        """
        effective_timeout = timeout if timeout is not None else self.timeout

        try:
            locator = self.page.get_by_text(section_text, exact=False)
            locator.first.wait_for(state="visible", timeout=effective_timeout)
            logger.debug(f"Section visible: '{section_text}'")
            return True
        except PlaywrightTimeoutError:
            page_url = self.page.url if self.page else ""
            logger.error(
                f"Timed out waiting for section '{section_text}' "
                f"(timeout: {effective_timeout}ms). URL: {page_url}"
            )
            raise ElementNotFoundError(
                description=f"Section containing text '{section_text}'",
                strategies_attempted=["wait_for_visible"],
                page_url=page_url,
            )

    # --- Private strategy methods ---

    def _try_exact_text(self, text: str, element_type: str) -> Optional[Locator]:
        """Try to find element by exact text match."""
        try:
            locator = self.page.get_by_text(text, exact=True)
            if locator.count() > 0 and locator.first.is_visible(timeout=2000):
                # For interactive elements, we may need the input itself, not the text node
                if element_type in ("radio", "checkbox"):
                    # Try to find the input within or near the text element
                    parent = locator.first.locator("..")
                    input_locator = parent.locator(f"input[type='{element_type}']")
                    if input_locator.count() > 0:
                        return input_locator.first
                return locator.first
        except (PlaywrightTimeoutError, Exception):
            pass
        return None

    def _try_label(self, label: str) -> Optional[Locator]:
        """Try to find element by label association."""
        try:
            locator = self.page.get_by_label(label)
            if locator.count() > 0 and locator.first.is_visible(timeout=2000):
                return locator.first
        except (PlaywrightTimeoutError, Exception):
            pass
        return None

    def _try_aria_label(self, aria_label: str) -> Optional[Locator]:
        """Try to find element by ARIA label attribute."""
        try:
            locator = self.page.locator(f"[aria-label='{aria_label}']")
            if locator.count() > 0 and locator.first.is_visible(timeout=2000):
                return locator.first
        except (PlaywrightTimeoutError, Exception):
            pass
        return None

    def _try_near_text(self, near_text: str, element_type: str) -> Optional[Locator]:
        """Try to find element by locating nearby text and traversing to interactive sibling."""
        try:
            text_locator = self.page.get_by_text(near_text, exact=False)
            if text_locator.count() == 0:
                return None

            # Map element types to selectors for interactive elements
            type_selectors = {
                "radio": "input[type='radio']",
                "checkbox": "input[type='checkbox']",
                "dropdown": "select",
                "text_input": "input[type='text'], input:not([type]), textarea",
                "file_input": "input[type='file']",
                "button": "button, input[type='submit'], [role='button']",
            }
            selector = type_selectors.get(element_type, "input, select, button, textarea")

            # Search within the parent element
            parent = text_locator.first.locator("..")
            interactive = parent.locator(selector)
            if interactive.count() > 0:
                return interactive.first

            # Try grandparent
            grandparent = parent.locator("..")
            interactive = grandparent.locator(selector)
            if interactive.count() > 0:
                return interactive.first

        except (PlaywrightTimeoutError, Exception):
            pass
        return None

    def _try_css_selector(self, selector: str) -> Optional[Locator]:
        """Try to find element by CSS selector."""
        try:
            locator = self.page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible(timeout=2000):
                return locator.first
        except (PlaywrightTimeoutError, Exception):
            pass
        return None

    def _try_partial_text(self, text: str, element_type: str) -> Optional[Locator]:
        """Try to find element by partial text match."""
        try:
            locator = self.page.get_by_text(text, exact=False)
            if locator.count() > 0 and locator.first.is_visible(timeout=2000):
                # For interactive elements, find the input itself
                if element_type in ("radio", "checkbox"):
                    parent = locator.first.locator("..")
                    input_locator = parent.locator(f"input[type='{element_type}']")
                    if input_locator.count() > 0:
                        return input_locator.first
                return locator.first
        except (PlaywrightTimeoutError, Exception):
            pass
        return None
