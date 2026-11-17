from __future__ import annotations

import re
import json
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.image_thumbnail_text_repo import (
    ImageThumbnailTextRepository,
)
from platform_api.routers.admin_image_prompts import (
    _decode_text,
    _normalize_prompt,
    _rows_from_csv,
    _rows_from_xls,
    _rows_from_xlsx,
)

router = APIRouter(prefix="/admin/thumbnail-texts", tags=["admin"])

TEXT_MAX_CHARS = 200
PLACEMENTS = {"top_center", "center", "bottom_center"}
ALIGNMENTS = {"center", "left", "right"}


async def _get_thumbnail_text_repo() -> ImageThumbnailTextRepository:
    raise NotImplementedError(
        "Thumbnail text repository dependency not configured. "
        "Wire via app.dependency_overrides."
    )


AdminDep = Annotated[AuthContext, Depends(require_admin)]
RepoDep = Annotated[ImageThumbnailTextRepository, Depends(_get_thumbnail_text_repo)]


class ThumbnailTextItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    subline: str | None = None
    placement: str
    alignment: str
    style_hint: str | None = None
    is_active: bool
    sort_order: int
    notes: str | None = None


class ThumbnailTextListResponse(BaseModel):
    items: list[ThumbnailTextItem]


class ThumbnailTextCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=TEXT_MAX_CHARS)
    subtitle: str | None = Field(default=None, max_length=TEXT_MAX_CHARS)
    subline: str | None = Field(default=None, max_length=TEXT_MAX_CHARS)
    placement: str = "top_center"
    alignment: str = "center"
    style_hint: str | None = Field(default=None, max_length=400)
    is_active: bool = True
    sort_order: int = 0
    notes: str | None = Field(default=None, max_length=1000)


class ThumbnailTextUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX_CHARS)
    subtitle: str | None = Field(default=None, max_length=TEXT_MAX_CHARS)
    subline: str | None = Field(default=None, max_length=TEXT_MAX_CHARS)
    placement: str | None = None
    alignment: str | None = None
    style_hint: str | None = Field(default=None, max_length=400)
    is_active: bool | None = None
    sort_order: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ThumbnailTextDeleteAllResponse(BaseModel):
    deleted: int


class ThumbnailTextImportResponse(BaseModel):
    inserted: int = 0
    skipped_existing: int = 0
    skipped_empty: int = 0
    errors: list[str] = Field(default_factory=list)


def _handle_storage_error(exc: Exception) -> None:
    if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
        raise HTTPException(
            status_code=503,
            detail="Thumbnail text storage is not available. Apply migration 210.",
        )
    if "image_thumbnail_texts" in str(exc).lower() and "does not exist" in str(exc).lower():
        raise HTTPException(
            status_code=503,
            detail="Thumbnail text storage is not available. Apply migration 210.",
        )


def _placement(value: str | None) -> str:
    normalized = str(value or "top_center").strip().lower()
    if normalized not in PLACEMENTS:
        raise HTTPException(
            status_code=422,
            detail="placement must be top_center, center, or bottom_center.",
        )
    return normalized


def _alignment(value: str | None) -> str:
    normalized = str(value or "center").strip().lower()
    if normalized not in ALIGNMENTS:
        raise HTTPException(
            status_code=422, detail="alignment must be center, left, or right."
        )
    return normalized


def _item(record: object) -> ThumbnailTextItem:
    return ThumbnailTextItem(
        id=str(getattr(record, "id")),
        title=str(getattr(record, "title", "")),
        subtitle=getattr(record, "subtitle", None),
        subline=getattr(record, "subline", None),
        placement=str(getattr(record, "placement", "top_center")),
        alignment=str(getattr(record, "alignment", "center")),
        style_hint=getattr(record, "style_hint", None),
        is_active=bool(getattr(record, "is_active", True)),
        sort_order=int(getattr(record, "sort_order", 0)),
        notes=getattr(record, "notes", None),
    )


def _key(title: str, subtitle: str, subline: str) -> tuple[str, str, str]:
    return (
        re.sub(r"\s+", " ", title).strip().lower(),
        re.sub(r"\s+", " ", subtitle).strip().lower(),
        re.sub(r"\s+", " ", subline).strip().lower(),
    )


@router.get("", response_model=ThumbnailTextListResponse)
async def list_thumbnail_texts(
    _ctx: AdminDep, repo: RepoDep
) -> ThumbnailTextListResponse:
    try:
        records = await repo.list_all()
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return ThumbnailTextListResponse(items=[_item(record) for record in records])


@router.post("", response_model=ThumbnailTextItem)
async def create_thumbnail_text(
    _ctx: AdminDep, repo: RepoDep, request: ThumbnailTextCreateRequest
) -> ThumbnailTextItem:
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title cannot be blank.")
    try:
        record = await repo.create(
            title=title,
            subtitle=(request.subtitle or "").strip() or None,
            subline=(request.subline or "").strip() or None,
            placement=_placement(request.placement),
            alignment=_alignment(request.alignment),
            style_hint=(request.style_hint or "").strip() or None,
            is_active=request.is_active,
            sort_order=int(request.sort_order or 0),
            notes=(request.notes or "").strip() or None,
        )
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if record is None:
        raise HTTPException(status_code=422, detail="Could not create thumbnail text.")
    return _item(record)


@router.patch("/{text_id}", response_model=ThumbnailTextItem)
async def update_thumbnail_text(
    _ctx: AdminDep,
    repo: RepoDep,
    text_id: str,
    request: ThumbnailTextUpdateRequest,
) -> ThumbnailTextItem:
    try:
        record = await repo.update(
            text_id,
            title=request.title.strip() if request.title is not None else None,
            subtitle=request.subtitle,
            subline=request.subline,
            placement=(
                _placement(request.placement)
                if request.placement is not None
                else None
            ),
            alignment=(
                _alignment(request.alignment)
                if request.alignment is not None
                else None
            ),
            style_hint=request.style_hint,
            is_active=request.is_active,
            sort_order=request.sort_order,
            notes=request.notes,
        )
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if record is None:
        raise HTTPException(status_code=404, detail="Thumbnail text not found.")
    return _item(record)


@router.delete("/{text_id}")
async def delete_thumbnail_text(
    _ctx: AdminDep, repo: RepoDep, text_id: str
) -> dict[str, bool]:
    try:
        deleted = await repo.delete(text_id)
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return {"ok": bool(deleted)}


@router.delete("", response_model=ThumbnailTextDeleteAllResponse)
async def delete_all_thumbnail_texts(
    _ctx: AdminDep, repo: RepoDep
) -> ThumbnailTextDeleteAllResponse:
    try:
        deleted = await repo.delete_all()
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return ThumbnailTextDeleteAllResponse(deleted=deleted)


def _rows_from_thumbnail_json(raw: bytes) -> list[list[object]]:
    data = json.loads(_decode_text(raw))
    if isinstance(data, dict):
        data = data.get("items") or data.get("texts") or data.get("rows") or [data]
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of rows or objects.")
    rows: list[list[object]] = []
    for item in data:
        if isinstance(item, dict):
            rows.append(
                [
                    item.get("title", ""),
                    item.get("subtitle", ""),
                    item.get("subline", ""),
                    item.get("placement", ""),
                ]
            )
        elif isinstance(item, (list, tuple)):
            rows.append(list(item))
        else:
            rows.append([item])
    return rows


def _import_rows(filename: str, raw: bytes) -> list[tuple[int, str, str, str, str]]:
    lower = str(filename or "").lower()
    if lower.endswith(".csv") or lower.endswith(".tsv"):
        rows = _rows_from_csv(raw)
    elif lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        rows = _rows_from_xlsx(raw)
    elif lower.endswith(".xls"):
        rows = _rows_from_xls(raw)
    elif lower.endswith(".json"):
        rows = _rows_from_thumbnail_json(raw)
    else:
        raise ValueError("Use a .csv, .xls, .xlsx, or .json file.")
    if not rows:
        return []
    header = [str(cell or "").strip().lower() for cell in rows[0]]
    has_header = "title" in header
    title_index = header.index("title") if "title" in header else 0
    subtitle_index = header.index("subtitle") if "subtitle" in header else 1
    subline_index = header.index("subline") if "subline" in header else 2
    placement_index = header.index("placement") if "placement" in header else None
    start = 1 if has_header else 0
    parsed: list[tuple[int, str, str, str, str]] = []
    for row_number, row in enumerate(rows[start:], start=start + 1):
        if not row or all(not str(cell or "").strip() for cell in row):
            continue
        def cell(index: int | None) -> str:
            if index is None or index >= len(row):
                return ""
            return _normalize_prompt(row[index])

        title = cell(title_index)
        subtitle = cell(subtitle_index)
        subline = cell(subline_index)
        placement = cell(placement_index) or "top_center"
        parsed.append((row_number, title, subtitle, subline, placement))
    return parsed


@router.post("/import", response_model=ThumbnailTextImportResponse)
async def import_thumbnail_texts(
    _ctx: AdminDep, repo: RepoDep, file: UploadFile = File(...)
) -> ThumbnailTextImportResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    try:
        rows = _import_rows(file.filename or "", raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read the upload: {type(exc).__name__}: {exc}",
        ) from exc

    try:
        existing = await repo.list_all()
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    existing_keys = {
        _key(record.title, record.subtitle or "", record.subline or "")
        for record in existing
    }
    result = ThumbnailTextImportResponse()
    for row_number, title, subtitle, subline, placement in rows:
        if not title:
            result.skipped_empty += 1
            continue
        if any(len(value) > TEXT_MAX_CHARS for value in (title, subtitle, subline)):
            result.errors.append(
                f"Row {row_number}: text exceeds {TEXT_MAX_CHARS} characters."
            )
            continue
        key = _key(title, subtitle, subline)
        if key in existing_keys:
            result.skipped_existing += 1
            continue
        try:
            record = await repo.create(
                title=title,
                subtitle=subtitle or None,
                subline=subline or None,
                placement=_placement(placement),
                alignment="center",
                sort_order=row_number,
                notes=f"Imported from {file.filename or 'upload'}",
            )
        except Exception as exc:
            _handle_storage_error(exc)
            result.errors.append(f"Row {row_number}: {type(exc).__name__}: {exc}")
            continue
        if record is None:
            result.errors.append(f"Row {row_number}: insert failed.")
            continue
        existing_keys.add(key)
        result.inserted += 1
    return result
