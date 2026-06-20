"""Image prompt preset management: list, load, save, delete."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...app.main_window import MainWindow


@dataclass(slots=True)
class ImagePromptPresetCoordinator:
    """Owns image prompt preset CRUD operations extracted from MainWindow.

    Encapsulates:
    - Listing presets by kind (background / thumbnail)
    - Loading a preset into the form
    - Saving (upsert) a preset
    - Deleting a preset
    """

    host: "MainWindow"

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_presets(self, *, kind: str) -> list[dict[str, Any]]:
        """Return prompt presets for the given kind."""
        from ...database.image_db import list_prompt_presets

        if not self.host.db_cfg:
            return []
        return list_prompt_presets(self.host.db_cfg, kind=kind)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_preset(self, *, kind: str, preset_id: int) -> dict[str, Any] | None:
        """Return a single preset dict by id, or None."""
        all_rows = self.list_presets(kind=kind)
        return next((x for x in all_rows if int(x.get("id", 0) or 0) == preset_id), None)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save_preset(
        self,
        *,
        preset_id: int | None,
        kind: str,
        name: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Upsert a prompt preset and return the saved row."""
        from ...database.image_db import upsert_prompt_preset

        saved = upsert_prompt_preset(
            self.host.db_cfg,
            preset_id=preset_id,
            kind=kind,
            name=name.strip(),
            prompt=prompt.strip(),
        )
        return saved

    # ------------------------------------------------------------------
    # Deleting
    # ------------------------------------------------------------------

    def delete_preset(self, preset_id: int) -> None:
        """Delete a prompt preset by id."""
        from ...database.image_db import delete_prompt_preset

        pid = int(preset_id or 0)
        if pid <= 0:
            return
        delete_prompt_preset(self.host.db_cfg, pid)
