"""Unit tests for reel template CRUD operations (Task 3.1).

Validates Requirements 8.1, 8.2, 8.3, 8.4:
- Create reel templates with kind='reel'
- Update reel templates without affecting video templates
- Delete reel templates without affecting video templates
- Store uid, name, source, template JSON, kind, and timestamp
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from python_app.features.templates.management import (
    create_reel_template,
    delete_reel_template,
    list_reel_templates,
    update_reel_template,
)

# The functions use lazy imports from ...database.persistence, so we patch at the source.
PERSISTENCE_MODULE = "python_app.database.persistence"


@pytest.fixture
def mock_db_cfg():
    """Provide a mock database config object."""
    return MagicMock()


class TestCreateReelTemplate:
    """Req 8.1, 8.4: Creating reel templates with kind='reel'."""

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_create_stores_kind_reel(self, mock_connect, mock_db_cfg):
        """Create passes kind='reel' to the DB upsert function — verifying SQL includes kind."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        tpl = {"style": "reel-vertical", "spectrumEnabled": True}
        create_reel_template(mock_db_cfg, "My Reel", tpl)

        # Verify SQL was executed with kind='reel'
        mock_cursor.execute.assert_called_once()
        sql_call_args = mock_cursor.execute.call_args
        sql = sql_call_args[0][0]
        params = sql_call_args[0][1]

        assert "kind" in sql
        # params: (template_id, name, source, json_str, kind)
        assert params[1] == "My Reel"
        assert params[2] == "user"
        assert params[4] == "reel"

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_create_generates_uid(self, mock_connect, mock_db_cfg):
        """Create generates a valid UUID when none provided."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        tpl = {"style": "classic"}
        uid = create_reel_template(mock_db_cfg, "Reel A", tpl)

        # uid is returned and is a non-empty string
        assert isinstance(uid, str)
        assert len(uid) > 0
        # Verify the uid was passed as first param to SQL
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == uid

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_create_uses_provided_uid(self, mock_connect, mock_db_cfg):
        """Create uses the explicitly provided uid."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        tpl = {"style": "reel-vertical"}
        uid = create_reel_template(mock_db_cfg, "Reel B", tpl, uid="custom-id-123")

        assert uid == "custom-id-123"
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == "custom-id-123"

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_create_stores_template_json(self, mock_connect, mock_db_cfg):
        """Create stores the full template JSON dict (serialized)."""
        import json

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        tpl = {
            "style": "reel-center",
            "spectrumEnabled": False,
            "logoSettings": {"enabled": True, "size": 150},
        }
        create_reel_template(mock_db_cfg, "Complex Reel", tpl)

        params = mock_cursor.execute.call_args[0][1]
        # The template is serialized as JSON in params[3]
        assert json.loads(params[3]) == tpl


class TestUpdateReelTemplate:
    """Req 8.2: Updating reel templates without affecting video templates."""

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_update_passes_kind_reel(self, mock_connect, mock_db_cfg):
        """Update always sets kind='reel' to preserve template type."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        tpl = {"style": "updated-reel"}
        update_reel_template(mock_db_cfg, "tpl-id-456", "Updated Reel", tpl)

        params = mock_cursor.execute.call_args[0][1]
        # params: (template_id, name, source, json_str, kind)
        assert params[0] == "tpl-id-456"
        assert params[1] == "Updated Reel"
        assert params[4] == "reel"

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_update_targets_specific_uid(self, mock_connect, mock_db_cfg):
        """Update targets only the specified template uid."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        update_reel_template(mock_db_cfg, "specific-uid", "Name", {})

        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == "specific-uid"


class TestDeleteReelTemplate:
    """Req 8.3: Deleting reel templates without affecting video templates."""

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_delete_targets_specific_uid(self, mock_connect, mock_db_cfg):
        """Delete targets only the specified template uid."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        delete_reel_template(mock_db_cfg, "reel-uid-789")

        params = mock_cursor.execute.call_args[0][1]
        assert params == ("reel-uid-789",)


class TestListReelTemplates:
    """Req 6.3: Listing reel templates with kind='reel' filter."""

    @patch(f"{PERSISTENCE_MODULE}.connect_db")
    def test_list_filters_by_kind_reel(self, mock_connect, mock_db_cfg):
        """List calls DB with kind='reel' filter in the WHERE clause."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = lambda _: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda *_: None
        mock_connect.return_value = mock_conn

        list_reel_templates(mock_db_cfg)

        sql_call_args = mock_cursor.execute.call_args
        sql = sql_call_args[0][0]
        params = sql_call_args[0][1]
        assert "kind" in sql.lower()
        assert params == ("reel",)
