from platform_api.routers import channel_setup


def test_build_prompt_with_variation_replaces_placeholders_and_role_note(monkeypatch) -> None:
    monkeypatch.setattr(channel_setup.random, "choice", lambda options: "Variation note.")

    result = channel_setup._build_prompt_with_variation(
        "Prompt for {genre}. Context: {description}",
        "logo",
        genre="EDM",
        role="primary",
        description="High-energy gym music",
    )

    assert "Prompt for EDM. Context: High-energy gym music" in result
    assert channel_setup._ROLE_NOTES["primary"] in result
    assert "Variation note." in result


def test_build_prompt_with_variation_adds_title_diversity_guidance(monkeypatch) -> None:
    monkeypatch.setattr(channel_setup.random, "choice", lambda options: "Fresh naming note.")

    result = channel_setup._build_prompt_with_variation(
        "Generate names for {genre}",
        "title",
        genre="Phonk",
        role="both",
    )

    assert channel_setup._ROLE_NOTES["both"] in result
    assert "Fresh naming note." in result
    assert "Return clearly distinct options" in result


def test_build_prompt_with_variation_returns_base_prompt_for_unknown_category() -> None:
    result = channel_setup._build_prompt_with_variation(
        "Prompt for {genre}. Context: {description}",
        "unknown",
        genre="Pop",
        description="Bright vocals",
    )

    assert result == "Prompt for Pop. Context: Bright vocals"
