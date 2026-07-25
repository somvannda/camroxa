"""Tests for workspace cache."""



from __future__ import annotations



import time



from shared.models.auth import ProfileResponse, UserMeResponse

from shared.models.platform import DashboardOverview, DashboardStatsResponse, PromptNameOption

from shared.services.workspace_cache import WorkspaceCache, cache_entry_is_fresh





def test_workspace_cache_core_flag() -> None:

    cache = WorkspaceCache()

    assert not cache.has_core()

    cache.apply_warmup(

        profiles=[

            ProfileResponse(

                id="p1",

                user_id="u1",

                name="A",

                folder_name="a",

                run_prefix="a",

            )

        ],

        settings_raw={"ffmpeg_path": "/bin/ffmpeg"},

    )

    assert cache.has_core()



    me, profiles, settings_raw, descriptions, structures, moods = cache.snapshot_core()

    assert len(profiles) == 1

    assert settings_raw["ffmpeg_path"] == "/bin/ffmpeg"

    assert descriptions == []

    assert structures == []

    assert moods == []





def test_dashboard_cache_freshness() -> None:

    cache = WorkspaceCache()

    overview = DashboardOverview(

        me=UserMeResponse(

            id="u1",

            email="user@example.com",

            email_confirmed=True,

            display_name="User",

            credit_balance=10,

        ),

        stats=DashboardStatsResponse(credits_spent=1),

    )

    cache.apply_dashboard(overview)

    assert cache.is_dashboard_fresh()

    assert cache.snapshot_dashboard() is overview





    def test_settings_workspace_cache_freshness() -> None:

        cache = WorkspaceCache()

        cache.apply_settings_workspace(

            profiles=[ProfileResponse(id="p1", user_id="u1", name="A")],

            settings_raw={"ffmpegPath": "/bin/ffmpeg"},

            description_options=[PromptNameOption(id="d1", name="Desc")],

            structure_options=[PromptNameOption(id="s1", name="Struct")],

            mood_options=[PromptNameOption(id="m1", name="Mood")],

            youtube_connections=[],

            my_description_items=[{"id": "d-user", "name": "Mine", "content": "Body"}],

            my_structure_items=[{"id": "s-user", "name": "Mine", "content": "[Verse]"}],

            my_mood_items=[{"id": "m-user", "name": "Mine", "content": "Warm"}],

        )

        assert cache.is_settings_workspace_fresh()

        youtube, fetched_at = cache.snapshot_settings_extras()

        assert youtube == []

        assert fetched_at > 0

        descriptions, structures, moods, prompt_fetched_at = cache.snapshot_my_prompt_items()

        assert len(descriptions) == 1

        assert len(structures) == 1

        assert len(moods) == 1

        assert prompt_fetched_at > 0





def test_content_pool_cache_freshness() -> None:

    cache = WorkspaceCache()

    payload = {"stats": None, "items": None}

    cache.apply_content_pool("openings", 0, payload)

    assert cache.is_content_pool_fresh("openings", 0)

    assert cache.snapshot_content_pool("openings", 0) == payload

    assert not cache.is_content_pool_fresh("titles", 0)





def test_cache_entry_is_fresh_respects_ttl() -> None:

    fetched_at = time.time() - 200

    assert not cache_entry_is_fresh(fetched_at, ttl=120.0)

    assert cache_entry_is_fresh(time.time(), ttl=120.0)


def test_image_sample_packs_cache_freshness() -> None:
    cache = WorkspaceCache()
    cache.apply_image_sample_packs([{"id": "pack-1", "name": "Pack"}])
    assert cache.is_image_sample_packs_fresh()
    assert len(cache.snapshot_image_sample_packs()) == 1


def test_workspace_cache_clear() -> None:
    cache = WorkspaceCache()
    cache.apply_warmup(
        me=UserMeResponse(
            id="u1",
            email="user@example.com",
            email_confirmed=True,
            display_name="User",
            credit_balance=10,
        ),
        profiles=[ProfileResponse(id="p1", user_id="u1", name="A")],
        settings_raw={"ffmpegPath": "/bin/ffmpeg"},
    )
    cache.apply_settings_workspace(
        profiles=[ProfileResponse(id="p1", user_id="u1", name="A")],
        settings_raw={"ffmpegPath": "/bin/ffmpeg"},
        youtube_connections=[{"profile_id": "p1"}],
    )
    cache.clear()
    assert not cache.has_core()
    assert not cache.is_settings_workspace_fresh()
    assert cache.snapshot_core()[0] is None
    assert cache.snapshot_settings_extras()[0] == []


def test_sample_library_scan_cache_freshness() -> None:
    cache = WorkspaceCache()
    cache.apply_sample_library_scan("/bg", "/th", bg_files=["a.png"], th_files=["b.png"])
    assert cache.is_sample_library_scan_fresh("/bg", "/th")
    assert cache.snapshot_sample_library_scan("/bg", "/th") == (["a.png"], ["b.png"])
    assert not cache.is_sample_library_scan_fresh("/other", "/th")

