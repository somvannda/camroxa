"""Compatibility re-exports for Profile workspace cards."""

from __future__ import annotations

from features.profile.widgets.account_card import AccountCard
from features.profile.widgets.channel_profiles import (
    EMPTY_PROFILES,
    LOADING_PROFILES,
    PROFILES_SUBTITLE,
    ChannelProfilesCard,
)
from features.profile.widgets.membership_card import MembershipCard
from features.profile.widgets.recent_activity import RecentActivityCard
from features.profile.widgets.usage_overview import UsageOverview

ActivityCard = UsageOverview

__all__ = [
    "AccountCard",
    "ActivityCard",
    "ChannelProfilesCard",
    "EMPTY_PROFILES",
    "LOADING_PROFILES",
    "MembershipCard",
    "PROFILES_SUBTITLE",
    "RecentActivityCard",
    "UsageOverview",
]
