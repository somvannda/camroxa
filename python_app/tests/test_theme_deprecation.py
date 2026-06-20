"""Test that legacy theme module functions emit deprecation warnings."""

import warnings

import pytest


class TestBuildUiTokensDeprecation:
    """Tests for build_ui_tokens() deprecation guard."""

    def test_emits_deprecation_warning(self) -> None:
        from python_app.app.theme import build_ui_tokens

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            build_ui_tokens()

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "build_ui_tokens() is deprecated" in str(w[0].message)
        assert "TokenRegistry.as_dict()" in str(w[0].message)

    def test_delegates_to_token_registry(self) -> None:
        from python_app.app.theme import build_ui_tokens
        from python_app.design_system.tokens import TokenRegistry

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = build_ui_tokens()

        expected = TokenRegistry().as_dict()
        assert result == expected

    def test_returns_dict_with_string_keys(self) -> None:
        from python_app.app.theme import build_ui_tokens

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = build_ui_tokens()

        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())

    def test_retains_original_signature(self) -> None:
        """build_ui_tokens() should accept no arguments."""
        import inspect
        from python_app.app.theme import build_ui_tokens

        sig = inspect.signature(build_ui_tokens)
        assert len(sig.parameters) == 0


class TestBuildAppStylesheetDeprecation:
    """Tests for build_app_stylesheet() deprecation guard."""

    def test_emits_deprecation_warning(self) -> None:
        from python_app.app.theme import build_app_stylesheet

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            build_app_stylesheet()

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "build_app_stylesheet() is deprecated" in str(w[0].message)
        assert "apply_theme()" in str(w[0].message)

    def test_returns_empty_string(self) -> None:
        from python_app.app.theme import build_app_stylesheet

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = build_app_stylesheet()

        assert result == ""

    def test_accepts_original_positional_args(self) -> None:
        """build_app_stylesheet() should still accept its original arguments."""
        from python_app.app.theme import build_app_stylesheet

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = build_app_stylesheet(
                {"app_bg": "#111a28"},
                "arrow.svg",
                "spin_up.svg",
                "spin_down.svg",
            )

        assert result == ""

    def test_accepts_kwargs(self) -> None:
        """build_app_stylesheet() should accept arbitrary kwargs for flexibility."""
        from python_app.app.theme import build_app_stylesheet

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = build_app_stylesheet(ui={}, arrow_url="x")

        assert result == ""
