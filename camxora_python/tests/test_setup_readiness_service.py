from __future__ import annotations

from shared.lib.music_readiness import evaluate_music_readiness
from shared.models.auth import ProfileResponse
from shared.models.platform import YouTubeConnectionResponse
from shared.services.setup_readiness_service import SetupReadinessService


def test_setup_readiness_service_incomplete_count() -> None:
    service = SetupReadinessService()
    profiles = [
        ProfileResponse(id="p1", user_id="u1", name="Primary"),
        ProfileResponse(id="p2", user_id="u1", name="Secondary"),
    ]
    report = evaluate_music_readiness(
        selected_profiles=profiles,
        settings={},
        youtube_connections=[],
    )
    service._apply_report(report)
    assert service.incomplete_count() > 0
