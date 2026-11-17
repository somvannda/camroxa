from __future__ import annotations

import json

from platform_api.routers.admin_thumbnail_texts import _import_rows


def test_import_rows_csv_with_header() -> None:
    rows = _import_rows(
        "texts.csv",
        b"title,subtitle,subline,placement\nBASS,CAR MUSIC,2026,top_center\n",
    )
    assert rows == [(2, "BASS", "CAR MUSIC", "2026", "top_center")]


def test_import_rows_csv_without_header() -> None:
    rows = _import_rows("texts.csv", b"BASS,CAR MUSIC,2026\n")
    assert rows == [(1, "BASS", "CAR MUSIC", "2026", "top_center")]


def test_import_rows_json_objects() -> None:
    rows = _import_rows(
        "texts.json",
        json.dumps(
            [{"title": "BASS", "subtitle": "CAR MUSIC", "subline": "2026"}]
        ).encode(),
    )
    assert rows == [(1, "BASS", "CAR MUSIC", "2026", "top_center")]
