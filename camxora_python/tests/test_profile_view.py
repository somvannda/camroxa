"""Profile view tests — requirements T-1 through T-5 plus search/filter."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_controls import StudioComboBox
from features.create.widgets.studio_panel import StudioPanel
from features.profile.views.profile_view import ProfileView
from features.profile.widgets.membership_metric_bar import MembershipMetricBar
from features.profile.widgets.profile_cards import EMPTY_PROFILES, LOADING_PROFILES
from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.platform import (
    DashboardOverview,
    DashboardStatsResponse,
    QuotaStatusResponse,
    ValidateLicenseResponse,
)
from shared.services.platform_api import PlatformApi


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _profile(
    *,
    profile_id: str = "profile-1",
    name: str = "OK Channel",
    run_prefix: str = "OK",
    visibility: str = "public",
) -> ProfileResponse:
    return ProfileResponse(
        id=profile_id,
        user_id="user-1",
        name=name,
        run_prefix=run_prefix,
        output_resolution="1920x1080",
        image_config={"mode": "bg_thumb"},
        youtube_config={"visibility": visibility},
    )


def _sample_overview(*, profiles: list[ProfileResponse] | None = None) -> DashboardOverview:
    if profiles is None:
        profiles = [_profile()]
    return DashboardOverview(
        me=UserMeResponse(
            id="user-1",
            email="boss@example.com",
            email_confirmed=True,
            display_name="Boss",
            credit_balance=250,
            plan_name="Pro",
            profile_allowance=5,
            channel_profile_count=2,
        ),
        profiles=profiles,
        license=ValidateLicenseResponse(
            plan_type="Pro",
            profile_allowance=5,
            monthly_song_quota=120,
            songs_remaining=76,
            wallet_balance=250,
            expiration_date="2026-12-31T00:00:00Z",
        ),
        stats=DashboardStatsResponse(
            credits_spent=480,
            credits_remaining=250,
            credits_total=730,
            songs_generated=44,
            songs_remaining=76,
            songs_quota=120,
            images_generated=19,
            videos_generated=3,
        ),
        quota=QuotaStatusResponse(
            songs_remaining=76,
            songs_quota=120,
        ),
    )


def test_profile_reuses_create_chrome(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    header = view.widget().findChild(CreateHeader)
    assert header is not None
    assert header.objectName() == "CreateHeader"
    assert view._profiles._add.objectName() == "TransportPrimary"
    assert view._profiles._add.isHidden()
    assert isinstance(view._profiles._visibility, StudioComboBox)
    assert view._account.objectName() == "Panel"
    assert isinstance(view._account, StudioPanel)
    assert isinstance(view._profiles, StudioPanel)
    assert isinstance(view._membership, StudioPanel)
    assert isinstance(view._usage, StudioPanel)
    assert isinstance(view._activity, StudioPanel)
    assert view._account.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert "#071426" in view.styleSheet()
    assert "QFrame#Panel" in view.styleSheet()
    assert view.widget().layout().contentsMargins().left() == 10


def test_loading_placeholders(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    view.show()
    assert view._account._display_name.text() == "Loading account..."
    assert view._account._email.text() == "Loading account email..."
    assert view._profiles._table.item(0, 0).text() == LOADING_PROFILES
    assert view._usage._songs._value.text() == "--"


def test_error_account_state(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    view._on_failed("network")
    assert view._account._email.text() == "Unable to load account information."
    assert view._account._session._value.text() == "Needs attention"
    assert view._profiles._table.item(0, 0).text() == EMPTY_PROFILES


def test_success_bind_membership_activity_and_profiles(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    view._apply_overview(_sample_overview())
    assert view._account._email_status._value.text() == "Confirmed"
    assert view._account._linked_profiles._value.text() == "OK Channel"
    assert view._account._folders._value.text() == "OK"
    assert "Camxora" in view._account._local_data._value.text()
    assert "Verified" in view._account._verification.text()
    assert view._membership._plan._value.text() == "Pro"
    assert view._membership._credits._value.text() == "250"
    assert "2026" in view._membership._expiry._value.text()
    assert "Dec" in view._membership._expiry._value.text()
    assert not hasattr(view._membership, "_songs_bar")
    assert not hasattr(view._membership, "_song_quota")
    assert view._membership._profiles_bar._value.text() == "2 / 5"
    assert view._profiles._table.item(0, 0).text() == "OK Channel"
    assert view._profiles._table.item(0, 3).text() == "Background + Thumbnail"
    assert view._profiles._table.item(0, 4).text() == "public"
    assert view._usage._images._value.text() == "19"


def test_empty_profiles(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    view._apply_overview(_sample_overview(profiles=[]))
    assert view._profiles._table.item(0, 0).text() == EMPTY_PROFILES


def test_membership_metric_bar_layout(qapp: QApplication) -> None:
    bar = MembershipMetricBar("Monthly songs", bar_color="sky")
    bar.set_metric("44 / 120", 37)
    assert bar._value.text() == "44 / 120"
    assert bar._bar.value() == 37
    assert "MONTHLY SONGS" in bar._label.text().upper()


def test_membership_shows_wallet_not_song_quota(qapp: QApplication) -> None:
    overview = _sample_overview()
    overview.license.wallet_balance = 0
    overview.me.credit_balance = 0
    view = ProfileView(PlatformApi())
    view._apply_overview(overview)
    assert view._membership._credits._value.text() == "0"
    assert not hasattr(view._membership, "_song_quota")


def test_search_filters_profile_rows(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    view._apply_overview(
        _sample_overview(
            profiles=[
                _profile(name="OK Channel", run_prefix="OK"),
                _profile(profile_id="profile-2", name="Bass Drive", run_prefix="BD", visibility="unlisted"),
            ]
        )
    )
    view._profiles._search.setText("bass")
    assert view._profiles._model.rowCount() == 1
    assert view._profiles._table.item(0, 0).text() == "Bass Drive"


def test_visibility_filter_hides_non_matching_rows(qapp: QApplication) -> None:
    view = ProfileView(PlatformApi())
    view._apply_overview(
        _sample_overview(
            profiles=[
                _profile(name="OK Channel", visibility="public"),
                _profile(profile_id="profile-2", name="Bass Drive", run_prefix="BD", visibility="unlisted"),
            ]
        )
    )
    view._profiles._visibility.setCurrentIndex(2)  # Unlisted
    assert view._profiles._model.rowCount() == 1
    assert view._profiles._table.item(0, 0).text() == "Bass Drive"
    assert view._profiles._table.item(0, 4).text() == "unlisted"
