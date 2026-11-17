from __future__ import annotations

import csv
import io
import json
import re
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRepository


router = APIRouter(prefix="/admin/image-prompts", tags=["admin"])

PROMPT_TEXT_MAX_CHARS = 20000
VALID_KINDS = {"background", "thumbnail"}


async def _get_image_prompt_repo() -> ImagePromptStyleRepository:
    raise NotImplementedError(
        "ImagePromptStyleRepository dependency not configured. Wire via app.dependency_overrides."
    )


AdminDep = Annotated[AuthContext, Depends(require_admin)]
RepoDep = Annotated[ImagePromptStyleRepository, Depends(_get_image_prompt_repo)]


class ImagePromptStyleItem(BaseModel):
    id: str
    kind: str
    name: str
    prompt_text: str
    text_template: str | None = None
    is_active: bool
    sort_order: int
    notes: str | None = None


class ImagePromptStyleListResponse(BaseModel):
    items: list[ImagePromptStyleItem]


class DeleteAllImagePromptsResponse(BaseModel):
    deleted: int
    kind: str


class ImagePromptStyleCreateRequest(BaseModel):
    kind: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=120)
    prompt_text: str = Field(..., min_length=1, max_length=PROMPT_TEXT_MAX_CHARS)
    text_template: str | None = Field(default=None, max_length=200)
    is_active: bool = True
    sort_order: int = 0
    notes: str | None = Field(default=None, max_length=1000)


class ImagePromptStyleUpdateRequest(BaseModel):
    kind: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_text: str | None = Field(default=None, min_length=1, max_length=PROMPT_TEXT_MAX_CHARS)
    text_template: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    sort_order: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


def _raise_migration_needed() -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            "Image prompt storage is not available yet because the database migration "
            "has not been applied. Run `python -m alembic -c platform_api/alembic.ini "
            "upgrade head` from the project root."
        ),
    )


def _handle_storage_error(exc: Exception) -> None:
    if isinstance(exc, asyncpg.exceptions.UndefinedTableError):
        _raise_migration_needed()
    if "image_prompt_styles" in str(exc).lower() and "does not exist" in str(exc).lower():
        _raise_migration_needed()


def _validate_kind(kind: str) -> str:
    value = str(kind or "").strip().lower()
    if value not in VALID_KINDS:
        raise HTTPException(status_code=422, detail="kind must be background or thumbnail.")
    return value


def _validate_text_template(kind: str, template: str | None) -> str | None:
    if template is None:
        return None
    value = str(template).strip()
    if not value:
        return ""
    if kind != "thumbnail":
        raise HTTPException(
            status_code=422,
            detail="text_template is only available for thumbnail styles.",
        )
    unknown = set(re.findall(r"\{([a-zA-Z_]+)\}", value)) - {"title", "album", "channel"}
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=(
                "Unknown text_template token(s): "
                + ", ".join(sorted(unknown))
                + ". Use {title}, {album}, or {channel}."
            ),
        )
    return value


def _item(record: object) -> ImagePromptStyleItem:
    return ImagePromptStyleItem(
        id=record.id,
        kind=record.kind,
        name=record.name,
        prompt_text=record.prompt_text,
        text_template=record.text_template,
        is_active=record.is_active,
        sort_order=record.sort_order,
        notes=record.notes,
    )


@router.get("", response_model=ImagePromptStyleListResponse)
async def list_image_prompts(
    _ctx: AdminDep,
    repo: RepoDep,
    kind: str | None = None,
) -> ImagePromptStyleListResponse:
    try:
        styles = await repo.list_all(kind=_validate_kind(kind) if kind else None)
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return ImagePromptStyleListResponse(items=[_item(style) for style in styles])


@router.delete("", response_model=DeleteAllImagePromptsResponse)
async def delete_all_image_prompts(
    _ctx: AdminDep,
    repo: RepoDep,
    kind: str,
) -> DeleteAllImagePromptsResponse:
    """Delete every prompt style of one kind. Existing image jobs keep their prompt."""
    kind_value = _validate_kind(kind)
    try:
        deleted = await repo.delete_all(kind=kind_value)
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    return DeleteAllImagePromptsResponse(deleted=deleted, kind=kind_value)


@router.post("", response_model=ImagePromptStyleItem)
async def create_image_prompt(
    _ctx: AdminDep,
    repo: RepoDep,
    request: ImagePromptStyleCreateRequest,
) -> ImagePromptStyleItem:
    kind = _validate_kind(request.kind)
    text_template = _validate_text_template(kind, request.text_template)
    prompt_text = request.prompt_text.strip()
    name = request.name.strip()
    if not prompt_text:
        raise HTTPException(status_code=422, detail="prompt_text cannot be blank.")
    if not name:
        raise HTTPException(status_code=422, detail="name cannot be blank.")
    try:
        style = await repo.create(
            kind=kind,
            name=name,
            prompt_text=prompt_text,
            text_template=text_template,
            is_active=request.is_active,
            sort_order=int(request.sort_order or 0),
            notes=(request.notes or "").strip() or None,
        )
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if style is None:
        raise HTTPException(status_code=500, detail="Could not create image prompt style.")
    return _item(style)


@router.patch("/{style_id}", response_model=ImagePromptStyleItem)
async def update_image_prompt(
    _ctx: AdminDep,
    repo: RepoDep,
    style_id: str,
    request: ImagePromptStyleUpdateRequest,
) -> ImagePromptStyleItem:
    kind = _validate_kind(request.kind) if request.kind else None
    if kind == "background":
        text_template = ""
    elif request.text_template is not None:
        text_template = _validate_text_template(kind or "thumbnail", request.text_template)
    else:
        text_template = None
    if request.name is not None and not request.name.strip():
        raise HTTPException(status_code=422, detail="name cannot be blank.")
    if request.prompt_text is not None and not request.prompt_text.strip():
        raise HTTPException(status_code=422, detail="prompt_text cannot be blank.")
    try:
        style = await repo.update(
            style_id,
            kind=kind,
            name=(
                request.name.strip() if request.name is not None else None
            ),
            prompt_text=(
                request.prompt_text.strip() if request.prompt_text is not None else None
            ),
            text_template=text_template,
            is_active=request.is_active,
            sort_order=request.sort_order,
            notes=(
                (request.notes or "").strip() or None
                if request.notes is not None
                else None
            ),
        )
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if style is None:
        raise HTTPException(status_code=404, detail="Image prompt style not found.")
    return _item(style)


@router.delete("/{style_id}")
async def delete_image_prompt(
    _ctx: AdminDep,
    repo: RepoDep,
    style_id: str,
) -> dict[str, bool]:
    try:
        deleted = await repo.delete(style_id)
    except Exception as exc:
        _handle_storage_error(exc)
        raise
    if not deleted:
        raise HTTPException(status_code=404, detail="Image prompt style not found.")
    return {"ok": True}

class ImagePromptImportResponse(BaseModel):
    inserted_background: int = 0
    inserted_thumbnail: int = 0
    skipped_existing: int = 0
    skipped_empty: int = 0
    errors: list[str] = Field(default_factory=list)


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _normalize_prompt(value: object) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _import_key(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _rows_from_csv(raw: bytes) -> list[list[object]]:
    text = _decode_text(raw)
    return [list(row) for row in csv.reader(io.StringIO(text))]


def _rows_from_xlsx(raw: bytes) -> list[list[object]]:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sheet = workbook.active
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def _rows_from_xls(raw: bytes) -> list[list[object]]:
    import xlrd

    workbook = xlrd.open_workbook(file_contents=raw)
    sheet = workbook.sheet_by_index(0)
    return [sheet.row_values(index) for index in range(sheet.nrows)]


def _rows_from_json(raw: bytes) -> list[list[object]]:
    data = json.loads(_decode_text(raw))
    if isinstance(data, dict):
        data = data.get("items") or data.get("prompts") or data.get("rows") or [data]
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of rows or objects.")
    rows: list[list[object]] = []
    for item in data:
        if isinstance(item, dict):
            rows.append(
                [
                    item.get("background", item.get("background_prompt", "")),
                    item.get("thumbnail", item.get("thumbnail_prompt", "")),
                ]
            )
        elif isinstance(item, (list, tuple)):
            rows.append(list(item))
        else:
            rows.append([item])
    return rows


def _import_rows(filename: str, raw: bytes) -> list[tuple[int, str, str]]:
    lower = str(filename or "").lower()
    if lower.endswith(".csv") or lower.endswith(".tsv"):
        rows = _rows_from_csv(raw)
    elif lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        rows = _rows_from_xlsx(raw)
    elif lower.endswith(".xls"):
        rows = _rows_from_xls(raw)
    elif lower.endswith(".json"):
        rows = _rows_from_json(raw)
    else:
        raise ValueError("Use a .csv, .xls, .xlsx, or .json file.")

    if not rows:
        return []

    header = [str(cell or "").strip().lower() for cell in rows[0]]
    has_header = any(cell in {"background", "thumbnail"} for cell in header)
    bg_index = header.index("background") if "background" in header else None
    th_index = header.index("thumbnail") if "thumbnail" in header else None
    start = 1 if has_header else 0
    parsed: list[tuple[int, str, str]] = []
    for row_number, row in enumerate(rows[start:], start=start + 1):
        if not row or all(not str(cell or "").strip() for cell in row):
            continue
        if bg_index is not None or th_index is not None:
            background = row[bg_index] if bg_index is not None and bg_index < len(row) else ""
            thumbnail = row[th_index] if th_index is not None and th_index < len(row) else ""
        elif len(row) >= 3:
            background, thumbnail = row[1], row[2]
        elif len(row) == 2:
            background, thumbnail = row[0], row[1]
        else:
            background, thumbnail = row[0], ""
        parsed.append(
            (
                row_number,
                _normalize_prompt(background),
                _normalize_prompt(thumbnail),
            )
        )
    return parsed


def _unique_name(base: str, existing: set[str]) -> str:
    candidate = base
    counter = 2
    while candidate.lower() in existing:
        candidate = f"{base} ({counter})"
        counter += 1
    existing.add(candidate.lower())
    return candidate


@router.post("/import", response_model=ImagePromptImportResponse)
async def import_image_prompts(
    _ctx: AdminDep,
    repo: RepoDep,
    file: UploadFile = File(...),
) -> ImagePromptImportResponse:
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
        (str(style.kind).lower(), _import_key(style.prompt_text))
        for style in existing
    }
    existing_names = {style.name.lower() for style in existing}
    result = ImagePromptImportResponse()

    for row_number, background, thumbnail in rows:
        for kind, text in (("background", background), ("thumbnail", thumbnail)):
            if not text:
                result.skipped_empty += 1
                continue
            if len(text) > PROMPT_TEXT_MAX_CHARS:
                result.errors.append(
                    f"Row {row_number} {kind}: prompt exceeds {PROMPT_TEXT_MAX_CHARS} characters."
                )
                continue
            key = (kind, _import_key(text))
            if key in existing_keys:
                result.skipped_existing += 1
                continue
            base = f"Imported {'BG' if kind == 'background' else 'TH'} {row_number:03d}"
            name = _unique_name(base, existing_names)
            try:
                created = await repo.create(
                    kind=kind,
                    name=name,
                    prompt_text=text,
                    is_active=True,
                    sort_order=row_number,
                    notes=f"Imported from {file.filename or 'upload'}",
                )
            except Exception as exc:
                _handle_storage_error(exc)
                result.errors.append(f"Row {row_number} {kind}: {type(exc).__name__}: {exc}")
                continue
            if created is None:
                result.errors.append(f"Row {row_number} {kind}: insert failed.")
                continue
            existing_keys.add(key)
            if kind == "background":
                result.inserted_background += 1
            else:
                result.inserted_thumbnail += 1

    return result
