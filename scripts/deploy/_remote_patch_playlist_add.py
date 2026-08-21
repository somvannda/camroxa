#!/usr/bin/env python3
"""Run on the VPS: surgical playlist-add patches. Do not replace phone layout."""
from __future__ import annotations

from pathlib import Path


def must_replace(path: Path, old: str, new: str, label: str) -> str:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing marker: {label}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {label}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    svc = Path("/opt/camxora/repo/platform_api/services/web_music_service.py")
    svc_text = svc.read_text(encoding="utf-8")
    if "async def list_playlist_memberships" not in svc_text:
        svc_text = must_replace(
            svc,
            "        return [self._playlist_payload(row, song_count=int(row[\"song_count\"] or 0)) for row in rows]\n\n    async def create_playlist(",
            """        return [self._playlist_payload(row, song_count=int(row["song_count"] or 0)) for row in rows]

    async def list_playlist_memberships(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            \"\"\"
            SELECT p.id AS playlist_id, p.name AS playlist_name, i.suno_task_id, i.variant
            FROM web_music_playlists p
            JOIN web_music_playlist_items i ON i.playlist_id = p.id
            WHERE p.user_id = $1
            ORDER BY p.updated_at DESC, i.position ASC, i.added_at ASC
            \"\"\",
            user_id,
        )
        return [
            {
                "playlist_id": str(row["playlist_id"]),
                "playlist_name": str(row["playlist_name"] or "Playlist"),
                "task_id": str(row["suno_task_id"]),
                "variant": str(row["variant"] or "ok"),
            }
            for row in rows
        ]

    async def create_playlist(""",
            "service memberships",
        )
    else:
        print("service memberships already patched")
        svc_text = svc.read_text(encoding="utf-8")

    old_ready = """            SELECT id, title, style, status, audio_url_ok, audio_url_alt, image_url_ok, image_url_alt
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            \"\"\",
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if task is None:
            raise NotFoundError("Generation not found.")
        if str(task["status"] or "").upper() != "SUCCESS":
            raise ValidationError("Only completed songs can be added to a playlist.")
        ready = bool(task["audio_url_ok"] if variant_key == "ok" else task["audio_url_alt"])
        if not ready:
            raise ValidationError("This song version is not ready yet.")"""
    new_ready = """            SELECT id, title, style, status, audio_url_ok, audio_url_alt,
                   image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt,
                   package_status_ok, package_status_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            \"\"\",
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if task is None:
            raise NotFoundError("Generation not found.")
        if str(task["status"] or "").upper() != "SUCCESS":
            raise ValidationError("Only completed songs can be added to a playlist.")
        ready = _clip_is_playable(task, variant=variant_key, task_id=task_id)
        if not ready:
            raise ValidationError("This song version is not ready yet.")"""
    if "ready = _clip_is_playable(task, variant=variant_key, task_id=task_id)" in svc_text:
        print("service ready check already patched")
    else:
        svc_text = must_replace(svc, old_ready, new_ready, "service ready check")

    old_ret = """            \"title\": str(task[\"title\"] or \"Untitled\"),
            \"style\": str(task[\"style\"] or \"\"),
            \"ready\": ready,
            \"audio_url\": await self._mint_owner_play_url(user_id, task_id, variant_key),"""
    # rewrite without over-escaping
    old_ret = '''            "title": str(task["title"] or "Untitled"),
            "style": str(task["style"] or ""),
            "ready": ready,
            "audio_url": await self._mint_owner_play_url(user_id, task_id, variant_key),'''
    new_ret = '''            "title": str(task["title"] or "Untitled"),
            "style": str(task["style"] or ""),
            "ready": ready,
            "package_status": str(
                _row_value(task, "package_status_ok" if variant_key == "ok" else "package_status_alt")
                or "none"
            ),
            "audio_url": await self._mint_owner_play_url(user_id, task_id, variant_key),'''
    svc_text = svc.read_text(encoding="utf-8")
    if '"package_status": str(' in svc_text and "add_playlist_item" in svc_text:
        # unique enough after ready patch
        if old_ret in svc_text:
            svc.write_text(svc_text.replace(old_ret, new_ret, 1), encoding="utf-8")
            print("patched add_playlist_item package_status")
        else:
            print("package_status already patched")
    else:
        if old_ret not in svc_text:
            raise SystemExit("service add return marker missing")
        svc.write_text(svc_text.replace(old_ret, new_ret, 1), encoding="utf-8")
        print("patched add_playlist_item package_status")

    router = Path("/opt/camxora/repo/platform_api/routers/web_music.py")
    rt = router.read_text(encoding="utf-8")
    if "class WebMusicPlaylistMembershipResponse" not in rt:
        must_replace(
            router,
            '''class WebMusicPlaylistItemListResponse(BaseModel):
    items: list[WebMusicPlaylistItemResponse] = Field(default_factory=list)


class WebMusicPlaylistAddItemRequest(BaseModel):''',
            '''class WebMusicPlaylistItemListResponse(BaseModel):
    items: list[WebMusicPlaylistItemResponse] = Field(default_factory=list)


class WebMusicPlaylistMembershipResponse(BaseModel):
    playlist_id: str
    playlist_name: str
    task_id: str
    variant: str


class WebMusicPlaylistMembershipListResponse(BaseModel):
    items: list[WebMusicPlaylistMembershipResponse] = Field(default_factory=list)


class WebMusicPlaylistAddItemRequest(BaseModel):''',
            "router models",
        )
    else:
        print("router models already patched")

    rt = router.read_text(encoding="utf-8")
    if '("/playlists/memberships"' not in rt:
        must_replace(
            router,
            '''    items = await service.list_playlists(UUID(ctx.user_id))
    return WebMusicPlaylistListResponse(items=[WebMusicPlaylistResponse(**item) for item in items])


@router.post("/playlists", response_model=WebMusicPlaylistResponse, status_code=201)''',
            '''    items = await service.list_playlists(UUID(ctx.user_id))
    return WebMusicPlaylistListResponse(items=[WebMusicPlaylistResponse(**item) for item in items])


@router.get("/playlists/memberships", response_model=WebMusicPlaylistMembershipListResponse)
async def list_playlist_memberships(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistMembershipListResponse:
    items = await service.list_playlist_memberships(UUID(ctx.user_id))
    return WebMusicPlaylistMembershipListResponse(
        items=[WebMusicPlaylistMembershipResponse(**item) for item in items]
    )


@router.post("/playlists", response_model=WebMusicPlaylistResponse, status_code=201)''',
            "router memberships route",
        )
    else:
        print("router memberships route already patched")

    api = Path("/opt/camxora/repo/music_web/src/lib/playlist-api.ts")
    api_text = api.read_text(encoding="utf-8")
    if "export type WebMusicPlaylistMembership" not in api_text:
        must_replace(
            api,
            '''  added_at?: string | null;
};

export type WebMusicPublicPlaylist = {''',
            '''  added_at?: string | null;
};

export type WebMusicPlaylistMembership = {
  playlist_id: string;
  playlist_name: string;
  task_id: string;
  variant: string;
};

export type WebMusicPublicPlaylist = {''',
            "playlist-api type",
        )
    api_text = api.read_text(encoding="utf-8")
    if "listWebMusicPlaylistMemberships" not in api_text:
        must_replace(
            api,
            '''  return response.json();
}

export async function createWebMusicPlaylist(input: {''',
            '''  return response.json();
}

export async function listWebMusicPlaylistMemberships(): Promise<{ items: WebMusicPlaylistMembership[] }> {
  const response = await musicAuthFetch('/api/v1/web-music/playlists/memberships');
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to load playlist songs'));
  }
  return response.json();
}

export async function createWebMusicPlaylist(input: {''',
            "playlist-api function",
        )
    else:
        print("playlist-api already patched")

    layout = Path("/opt/camxora/repo/music_web/src/app/layout.tsx")
    lt = layout.read_text(encoding="utf-8")
    if "PlaylistMembershipsProvider" not in lt:
        if "import { LikesProvider } from '@/components/likes-provider';" not in lt:
            raise SystemExit("layout likes import missing")
        lt = lt.replace(
            "import { LikesProvider } from '@/components/likes-provider';\n",
            "import { LikesProvider } from '@/components/likes-provider';\nimport { PlaylistMembershipsProvider } from '@/components/playlist-memberships-provider';\n",
            1,
        )
        old = """            <LikesProvider>
              <ShellSwitcher>{children}</ShellSwitcher>
            </LikesProvider>"""
        new = """            <LikesProvider>
              <PlaylistMembershipsProvider>
                <ShellSwitcher>{children}</ShellSwitcher>
              </PlaylistMembershipsProvider>
            </LikesProvider>"""
        if old not in lt:
            raise SystemExit("layout provider wrap marker missing")
        layout.write_text(lt.replace(old, new, 1), encoding="utf-8")
        print("patched layout.tsx (viewport preserved)")
    else:
        print("layout already patched")

    css = Path("/opt/camxora/repo/music_web/src/app/globals.css")
    css_text = css.read_text(encoding="utf-8")
    if "playlist-tick-pop" not in css_text:
        css.write_text(
            css_text.rstrip()
            + """

@keyframes playlist-tick-pop {
  0% { transform: scale(0.35) rotate(-12deg); opacity: 0; }
  55% { transform: scale(1.18) rotate(0deg); opacity: 1; }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}
@keyframes playlist-chip-in {
  0% { transform: translateY(5px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
}
@keyframes playlist-row-flash {
  0% { background-color: rgba(52, 211, 153, 0.18); }
  100% { background-color: transparent; }
}
.playlist-tick-pop { animation: playlist-tick-pop 420ms cubic-bezier(0.22, 1.35, 0.36, 1); }
.playlist-chip-in { animation: playlist-chip-in 280ms ease-out; }
.playlist-row-flash { animation: playlist-row-flash 700ms ease-out; }
""",
            encoding="utf-8",
        )
        print("patched globals.css")
    else:
        print("globals.css already patched")

    create = Path("/opt/camxora/repo/music_web/src/components/create-page-client.tsx")
    ct = create.read_text(encoding="utf-8")
    if "ClipPlaylistNames" not in ct:
        if "import { AddToPlaylistButton } from '@/components/add-to-playlist-button';" not in ct:
            raise SystemExit("create-page AddToPlaylistButton import missing")
        ct = ct.replace(
            "import { AddToPlaylistButton } from '@/components/add-to-playlist-button';",
            "import { AddToPlaylistButton, ClipPlaylistNames } from '@/components/add-to-playlist-button';",
            1,
        )
        old = """                          <ClipReadyLabel
                            clip={clip}
                            model={generation.model}
                            waitingLabel={clipWaitingLabel(generation)}
                            generating={isGeneratingStatus(generation)}
                          />"""
        new = """                          <ClipReadyLabel
                            clip={clip}
                            model={generation.model}
                            waitingLabel={clipWaitingLabel(generation)}
                            generating={isGeneratingStatus(generation)}
                          />
                          <ClipPlaylistNames taskId={generation.id} variant={clip.variant} className="mt-1" />"""
        if old not in ct:
            raise SystemExit("create-page row ClipReadyLabel marker missing")
        ct = ct.replace(old, new, 1)
        old = """                <ClipReadyLabel
                  clip={selectedVersion.clip}
                  model={selectedVersion.song.model}
                  waitingLabel={clipWaitingLabel(selectedVersion.song)}
                  className="text-sm text-slate-400"
                />"""
        new = """                <ClipReadyLabel
                  clip={selectedVersion.clip}
                  model={selectedVersion.song.model}
                  waitingLabel={clipWaitingLabel(selectedVersion.song)}
                  className="text-sm text-slate-400"
                />
                <ClipPlaylistNames
                  taskId={selectedVersion.song.id}
                  variant={selectedVersion.clip.variant}
                  className="mt-1.5"
                />"""
        if old not in ct:
            raise SystemExit("create-page sidebar ClipReadyLabel marker missing")
        create.write_text(ct.replace(old, new, 1), encoding="utf-8")
        print("patched create-page-client.tsx")
    else:
        print("create-page already patched")

    print("PATCH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
