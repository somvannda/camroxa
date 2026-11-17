from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from platform_api.routers.admin_image_prompts import (
    _import_key,
    _import_rows,
    _unique_name,
)


def test_import_rows_csv_with_header() -> None:
    raw = b"#,background,thumbnail\n1,BG one,TH one\n2,BG two,TH two\n"
    rows = _import_rows("prompts.csv", raw)
    assert rows == [
        (2, "BG one", "TH one"),
        (3, "BG two", "TH two"),
    ]


def test_import_rows_csv_without_header() -> None:
    raw = b"1,BG one,TH one\n2,BG two,TH two\n"
    rows = _import_rows("prompts.csv", raw)
    assert rows == [
        (1, "BG one", "TH one"),
        (2, "BG two", "TH two"),
    ]


def test_import_rows_json_objects() -> None:
    raw = json.dumps(
        [{"background": "BG one", "thumbnail": "TH one"}]
    ).encode()
    rows = _import_rows("prompts.json", raw)
    assert rows == [(1, "BG one", "TH one")]


def test_import_rows_xlsx() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["#", "background", "thumbnail"])
    sheet.append([1, "BG one", "TH one"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    rows = _import_rows("prompts.xlsx", buffer.getvalue())
    assert rows == [(2, "BG one", "TH one")]


def test_import_key_normalizes_case_and_whitespace() -> None:
    assert _import_key("  Neon   Night\nDrive ") == "neon night drive"


def test_unique_name_appends_suffix() -> None:
    existing = {"imported bg 001"}
    assert _unique_name("Imported BG 001", existing) == "Imported BG 001 (2)"


def test_admin_downloadable_templates_parse_with_importer() -> None:
    templates = (
        Path(__file__).resolve().parents[2]
        / "admin_portal"
        / "public"
        / "templates"
    )
    expected = (
        "EXAMPLE: Replace this with your background prompt",
        "EXAMPLE: Replace this with the thumbnail prompt",
    )
    for name in (
        "image-prompts-template.csv",
        "image-prompts-template.xls",
        "image-prompts-template.xlsx",
        "image-prompts-template.json",
    ):
        rows = _import_rows(name, (templates / name).read_bytes())
        assert len(rows) == 1, name
        assert rows[0][1:] == expected, name

class _Upload:
    filename = "prompts.csv"

    def __init__(self, raw: bytes):
        self._raw = raw

    async def read(self) -> bytes:
        return self._raw


class _FakeRepo:
    def __init__(self):
        self.created: list[dict] = []

    async def list_all(self):
        return [
            type(
                "Style",
                (),
                {
                    "kind": "background",
                    "prompt_text": "Existing prompt",
                    "name": "Existing",
                },
            )()
        ]

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return type("Created", (), {"id": "new-id"})()


@pytest.mark.asyncio
async def test_import_endpoint_skips_duplicates_and_inserts_new() -> None:
    from platform_api.routers.admin_image_prompts import import_image_prompts

    raw = (
        b"#,background,thumbnail\n"
        b"1,Existing   prompt,New TH\n"
        b"2,New BG,New TH\n"
    )
    repo = _FakeRepo()
    result = await import_image_prompts(None, repo, _Upload(raw))

    assert result.inserted_background == 1
    assert result.inserted_thumbnail == 1
    assert result.skipped_existing == 2  # Existing BG + duplicate New TH
    assert len(repo.created) == 2


@pytest.mark.asyncio
async def test_import_accepts_prompt_longer_than_old_3000_limit() -> None:
    from platform_api.routers.admin_image_prompts import import_image_prompts

    long_text = "a" * 5000
    raw = f"#,background,thumbnail\n1,{long_text},{long_text}\n".encode()
    repo = _FakeRepo()
    result = await import_image_prompts(None, repo, _Upload(raw))

    assert result.errors == []
    assert result.inserted_background == 1
    assert result.inserted_thumbnail == 1


@pytest.mark.asyncio
async def test_import_rejects_prompt_over_20000_limit() -> None:
    from platform_api.routers.admin_image_prompts import import_image_prompts

    long_text = "a" * 20001
    raw = f"#,background,thumbnail\n1,{long_text},{long_text}\n".encode()
    repo = _FakeRepo()
    result = await import_image_prompts(None, repo, _Upload(raw))

    assert result.inserted_background == 0
    assert result.inserted_thumbnail == 0
    assert len(result.errors) == 2
    assert "20000 characters" in result.errors[0]
