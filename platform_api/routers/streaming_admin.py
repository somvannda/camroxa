"""Admin music streaming management API for admin_portal."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.streaming_catalog_service import StreamingCatalogService
from platform_api.services.streaming_config_service import (
    get_streaming_storage_config_public,
    resolve_streaming_storage_config,
    save_streaming_storage_config,
)
from platform_api.services.streaming_metadata_sync_service import StreamingMetadataSyncService
from platform_api.services.streaming_upload_service import StreamingUploadService
from platform_api.services.music_genre_utils import parse_genre_list

router = APIRouter(prefix="/admin/streaming", tags=["streaming-admin"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


async def _get_catalog_service() -> StreamingCatalogService:
    raise NotImplementedError("StreamingCatalogService dependency not configured.")


CatalogServiceDep = Annotated[StreamingCatalogService, Depends(_get_catalog_service)]


class StreamingStorageConfigResponse(BaseModel):
    bucket: str
    region: str
    endpoint: str
    cdn_base_url: str
    stream_url_ttl_seconds: int
    key_id_masked: str
    application_key_masked: str
    secret_source: str
    configured: bool


class UpdateStreamingStorageConfigRequest(BaseModel):
    key_id: str = Field(default="", max_length=128)
    application_key: str = Field(default="", max_length=512)
    bucket: str = Field(default="camxora-media", max_length=128)
    region: str = Field(default="us-west-004", max_length=64)
    endpoint: str = Field(default="", max_length=512)
    cdn_base_url: str = Field(default="", max_length=512)
    stream_url_ttl_seconds: int = Field(default=3600, ge=300, le=86400)


class CatalogTrackResponse(BaseModel):
    id: str
    title: str
    album_name: str
    artist_name: str | None = None
    variant: str
    publish_status: str
    storage_key: str
    genre: str | None = None
    genres: list[str] = Field(default_factory=list)
    duration_seconds: float | None = None
    cover_url: str | None = None
    has_lyrics: bool = False
    suno_image_url: str | None = None
    created_at: str | None = None


class CatalogListResponse(BaseModel):
    items: list[CatalogTrackResponse]


class CatalogAlbumResponse(BaseModel):
    id: str
    album_name: str
    artist_name: str | None = None
    track_count: int
    published_track_count: int
    publish_status: str
    genre: str | None = None
    genres: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    cover_storage_key: str | None = None
    created_at: str | None = None


class CatalogAlbumListResponse(BaseModel):
    items: list[CatalogAlbumResponse]


class UploadJobResponse(BaseModel):
    id: str
    kind: str
    status: str
    source_url: str | None = None
    storage_key: str | None = None
    error: str | None = None
    created_at: str | None = None


class UploadJobListResponse(BaseModel):
    items: list[UploadJobResponse]


class UpdateTrackGenreRequest(BaseModel):
    genre: str = Field(..., min_length=1, max_length=128)


class MetadataSyncResponse(BaseModel):
    ok: bool
    track_id: str | None = None
    genre: str | None = None
    genres: list[str] | None = None
    duration_seconds: float | None = None
    has_lyrics: bool | None = None
    refreshed_from_suno: bool | None = None


class BulkMetadataSyncResponse(BaseModel):
    ok: bool
    synced: int
    failed: list[dict[str, str]]
    total: int


async def _admin_cover_url(pool: Any, storage_key: str | None) -> str | None:
    if not storage_key:
        return None
    service = StreamingCatalogService(pool)
    return await service._cover_url(storage_key)


def _track_cover_key(row: dict) -> str | None:
    return row.get("cover_storage_key") or row.get("album_cover_storage_key")


def _track_genres(row: dict) -> list[str]:
    genres = parse_genre_list(row.get("genres"))
    if genres:
        return genres
    genre = str(row.get("genre") or row.get("album_genre") or "").strip()
    return [genre] if genre else []


def _track_genre(row: dict) -> str | None:
    genres = _track_genres(row)
    return genres[0] if genres else None


def _album_genres(row: dict) -> list[str]:
    genres = parse_genre_list(row.get("genres"))
    if genres:
        return genres
    genre = str(row.get("genre") or "").strip()
    return [genre] if genre else None


def _build_catalog_track_response(row: dict, *, cover_url: str | None) -> CatalogTrackResponse:
    genres = _track_genres(row)
    lyrics = str(row.get("lyrics") or "").strip()
    return CatalogTrackResponse(
        id=str(row["id"]),
        title=str(row["title"]),
        album_name=str(row["album_name"]),
        artist_name=row.get("artist_name"),
        variant=str(row["variant"]),
        publish_status=str(row["publish_status"]),
        storage_key=str(row["storage_key"]),
        genre=genres[0] if genres else None,
        genres=genres,
        duration_seconds=row.get("duration_seconds"),
        cover_url=cover_url,
        has_lyrics=bool(lyrics),
        suno_image_url=row.get("suno_image_url"),
        created_at=row["created_at"].isoformat() if row.get("created_at") else None,
    )


@router.get("/config", response_model=StreamingStorageConfigResponse)
async def get_streaming_config(ctx: AdminDep) -> StreamingStorageConfigResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    config = await get_streaming_storage_config_public(get_db_pool())
    return StreamingStorageConfigResponse.model_validate(asdict(config))


@router.put("/config", response_model=StreamingStorageConfigResponse)
async def update_streaming_config(
    request: UpdateStreamingStorageConfigRequest,
    ctx: AdminDep,
) -> StreamingStorageConfigResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    current = await resolve_streaming_storage_config(pool)
    key_id = request.key_id.strip() or current.key_id
    application_key = request.application_key.strip() or current.application_key
    if not key_id:
        raise ValidationError("Application Key ID is required.")
    if not application_key:
        raise ValidationError("Application Key is required for the first save.")

    config = await save_streaming_storage_config(
        pool,
        key_id=key_id,
        application_key=application_key,
        bucket=request.bucket.strip() or current.bucket,
        region=request.region.strip() or current.region,
        endpoint=request.endpoint.strip() or current.endpoint,
        cdn_base_url=request.cdn_base_url.strip() or current.cdn_base_url,
        stream_url_ttl_seconds=request.stream_url_ttl_seconds,
    )
    return StreamingStorageConfigResponse.model_validate(asdict(config))


@router.get("/catalog", response_model=CatalogListResponse)
async def list_streaming_catalog(ctx: AdminDep, limit: int = 100) -> CatalogListResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await StreamingRepository(pool).list_admin_catalog(limit=max(1, min(limit, 500)))
    items: list[CatalogTrackResponse] = []
    for row in rows:
        cover_url = await _admin_cover_url(pool, _track_cover_key(row))
        items.append(_build_catalog_track_response(row, cover_url=cover_url))
    return CatalogListResponse(items=items)


@router.get("/catalog/albums", response_model=CatalogAlbumListResponse)
async def list_streaming_albums(ctx: AdminDep, limit: int = 100) -> CatalogAlbumListResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await StreamingRepository(pool).list_admin_albums(limit=max(1, min(limit, 500)))
    items: list[CatalogAlbumResponse] = []
    for row in rows:
        cover_storage_key = row.get("cover_storage_key")
        genres = _album_genres(row)
        items.append(
            CatalogAlbumResponse(
                id=str(row["id"]),
                album_name=str(row["album_name"]),
                artist_name=row.get("artist_name"),
                track_count=int(row.get("track_count") or 0),
                published_track_count=int(row.get("published_track_count") or 0),
                publish_status=str(row["publish_status"]),
                genre=genres[0] if genres else None,
                genres=genres,
                cover_url=await _admin_cover_url(pool, cover_storage_key),
                cover_storage_key=cover_storage_key,
                created_at=row["created_at"].isoformat() if row.get("created_at") else None,
            )
        )
    return CatalogAlbumListResponse(items=items)


@router.get("/upload-jobs", response_model=UploadJobListResponse)
async def list_streaming_upload_jobs(
    ctx: AdminDep,
    status: str | None = None,
    limit: int = 50,
) -> UploadJobListResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    rows = await StreamingRepository(get_db_pool()).list_upload_jobs(
        limit=max(1, min(limit, 200)),
        status=status,
    )
    items = [
        UploadJobResponse(
            id=str(row["id"]),
            kind=str(row["kind"]),
            status=str(row["status"]),
            source_url=row.get("source_url"),
            storage_key=row.get("storage_key"),
            error=row.get("error"),
            created_at=row["created_at"].isoformat() if row.get("created_at") else None,
        )
        for row in rows
    ]
    return UploadJobListResponse(items=items)


@router.post("/tracks/{track_id}/unpublish")
async def unpublish_stream_track(track_id: UUID, ctx: AdminDep, service: CatalogServiceDep) -> dict:
    del ctx
    if not await service.unpublish_track(track_id):
        raise NotFoundError("Track not found.")
    return {"ok": True}


@router.post("/tracks/{track_id}/republish")
async def republish_stream_track(track_id: UUID, ctx: AdminDep, service: CatalogServiceDep) -> dict:
    del ctx
    if not await service.republish_track(track_id):
        raise NotFoundError("Track not found.")
    return {"ok": True}


@router.delete("/tracks/{track_id}")
async def delete_stream_track(track_id: UUID, ctx: AdminDep, service: CatalogServiceDep) -> dict:
    del ctx
    if not await service.delete_track(track_id):
        raise NotFoundError("Track not found.")
    return {"ok": True}


@router.post("/albums/{album_id}/unpublish")
async def unpublish_stream_album(album_id: UUID, ctx: AdminDep, service: CatalogServiceDep) -> dict:
    del ctx
    if not await service.unpublish_album(album_id):
        raise NotFoundError("Album not found.")
    return {"ok": True}


@router.post("/albums/{album_id}/republish")
async def republish_stream_album(album_id: UUID, ctx: AdminDep, service: CatalogServiceDep) -> dict:
    del ctx
    if not await service.republish_album(album_id):
        raise NotFoundError("Album not found or has no published tracks.")
    return {"ok": True}


@router.delete("/albums/{album_id}")
async def delete_stream_album(album_id: UUID, ctx: AdminDep, service: CatalogServiceDep) -> dict:
    del ctx
    if not await service.delete_album(album_id):
        raise NotFoundError("Album not found.")
    return {"ok": True}


@router.post("/upload-jobs/{job_id}/retry")
async def retry_streaming_upload_job(job_id: UUID, ctx: AdminDep) -> dict:
    del ctx
    from platform_api.dependencies import get_db_pool

    try:
        return await StreamingUploadService(get_db_pool()).retry_failed_job(job_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise NotFoundError(message) from exc
        raise ValidationError(message) from exc


@router.post("/tracks/{track_id}/sync-metadata", response_model=MetadataSyncResponse)
async def sync_stream_track_metadata(track_id: UUID, ctx: AdminDep) -> MetadataSyncResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    service = StreamingMetadataSyncService(get_db_pool())
    try:
        result = await service.sync_track_metadata(track_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise NotFoundError(message) from exc
        raise ValidationError(message) from exc
    return MetadataSyncResponse.model_validate(result)


@router.post("/catalog/sync-metadata", response_model=BulkMetadataSyncResponse)
async def sync_all_stream_metadata(
    ctx: AdminDep,
    limit: int = 100,
) -> BulkMetadataSyncResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    result = await StreamingMetadataSyncService(get_db_pool()).sync_all_tracks_metadata(
        limit=max(1, min(limit, 500)),
    )
    return BulkMetadataSyncResponse.model_validate(result)


@router.patch("/tracks/{track_id}", response_model=CatalogTrackResponse)
async def update_stream_track(
    track_id: UUID,
    request: UpdateTrackGenreRequest,
    ctx: AdminDep,
) -> CatalogTrackResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    repo = StreamingRepository(pool)
    if not await repo.update_track_genre(track_id, request.genre):
        raise NotFoundError("Track not found.")

    rows = await repo.list_admin_catalog(limit=500)
    row = next((item for item in rows if str(item["id"]) == str(track_id)), None)
    if row is None:
        raise NotFoundError("Track not found.")

    cover_url = await _admin_cover_url(pool, _track_cover_key(row))
    return _build_catalog_track_response(row, cover_url=cover_url)
