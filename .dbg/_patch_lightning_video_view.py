from __future__ import annotations

from pathlib import Path

path = Path("camxora_python/features/video/views/video_view.py")
text = path.read_text(encoding="utf-8")
orig = text


def must_replace(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f"missing block: {label}")
    text = text.replace(old, new, 1)


if "LightningInspector" not in text:
    must_replace(
        "from features.video.widgets.spectrum_inspector import SpectrumInspector\n",
        "from features.video.widgets.spectrum_inspector import SpectrumInspector\n"
        "from features.video.widgets.lightning_inspector import LightningInspector\n",
        "spectrum import",
    )

if "self._lightning_layers" not in text:
    must_replace(
        "        self._spectrum_layers: list[dict] = []\n"
        "        self._selected_spectrum_layer_index = 0\n",
        "        self._spectrum_layers: list[dict] = []\n"
        "        self._selected_spectrum_layer_index = 0\n"
        "        self._lightning_layers: list[dict] = []\n"
        "        self._selected_lightning_layer_index = 0\n",
        "spectrum layers init",
    )

if "self._lightning_inspector" not in text:
    must_replace(
        """        self._particles_inspector = ParticlesInspector()
        self._particles_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._particles_inspector.preset_apply_requested.connect(self._apply_particle_preset)
        self._particles_inspector.preset_restore_requested.connect(self._restore_particle_preset)

        self._domain_inspectors = {
            "spectrum": self._spectrum_inspector,
            "background": self._background_inspector,
            "logo": self._logo_inspector,
            "particles": self._particles_inspector,
        }
""",
        """        self._particles_inspector = ParticlesInspector()
        self._particles_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._particles_inspector.preset_apply_requested.connect(self._apply_particle_preset)
        self._particles_inspector.preset_restore_requested.connect(self._restore_particle_preset)

        self._lightning_inspector = LightningInspector()
        self._lightning_inspector.draft_patch_requested.connect(self._patch_template_draft)
        self._lightning_inspector.layer_patch_requested.connect(self._patch_selected_lightning_layer)
        self._lightning_inspector.layer_add_requested.connect(self._add_lightning_layer)
        self._lightning_inspector.layer_duplicate_requested.connect(self._duplicate_lightning_layer)
        self._lightning_inspector.layer_delete_requested.connect(self._delete_lightning_layer)
        self._lightning_inspector.layer_move_up_requested.connect(self._move_lightning_layer_up)
        self._lightning_inspector.layer_move_down_requested.connect(self._move_lightning_layer_down)
        self._lightning_inspector.layer_selected.connect(self._select_lightning_layer)

        self._domain_inspectors = {
            "spectrum": self._spectrum_inspector,
            "background": self._background_inspector,
            "logo": self._logo_inspector,
            "particles": self._particles_inspector,
            "lightning": self._lightning_inspector,
        }
""",
        "particles + domain inspectors",
    )

old_combo = 'show_apply_combo=domain not in {"spectrum", "particles", "background", "logo"},'
new_combo = 'show_apply_combo=domain not in {"spectrum", "particles", "background", "logo", "lightning"},'
if old_combo in text:
    text = text.replace(old_combo, new_combo, 1)

if "lightning_position_changed.connect" not in text:
    must_replace(
        "        self._stage.spectrum_position_changed.connect(self._on_preview_spectrum_position_changed)\n",
        "        self._stage.spectrum_position_changed.connect(self._on_preview_spectrum_position_changed)\n"
        "        self._stage.lightning_position_changed.connect(self._on_preview_lightning_position_changed)\n",
        "stage spectrum position connect",
    )

# bind inspectors
if "self._lightning_inspector.bind_draft" not in text:
    must_replace(
        """        self._particles_inspector.bind_draft(self._template_draft)

        track_paths = self._current_track_paths()
""",
        """        self._particles_inspector.bind_draft(self._template_draft)
        self._lightning_inspector.bind_draft(
            self._template_draft,
            layers=self._lightning_layers,
            selected_layer_index=self._selected_lightning_layer_index,
        )

        track_paths = self._current_track_paths()
""",
        "bind particles",
    )

# hydrate lightning layers
if 'snapshot.get("lightningLayers")' not in text and "lightningLayers" not in text[text.find("_hydrate_draft_from_workspace"): text.find("_hydrate_draft_from_workspace") + 2500]:
    must_replace(
        """        if snapshot:
            self._template_draft = snapshot["draft"]
            self._template_name_draft = str(snapshot.get("templateName") or self._workspace.template_name)
            layers = snapshot.get("layers")
            self._spectrum_layers = clone_layer_records(layers) if layers else clone_layer_records(template.get("layers"))
        else:
            self._template_draft = persisted_draft
            self._template_name_draft = self._workspace.template_name
            self._spectrum_layers = clone_layer_records(template.get("layers"))
""",
        """        if snapshot:
            self._template_draft = snapshot["draft"]
            self._template_name_draft = str(snapshot.get("templateName") or self._workspace.template_name)
            layers = snapshot.get("layers")
            self._spectrum_layers = clone_layer_records(layers) if layers else clone_layer_records(template.get("layers"))
            lightning_layers = snapshot.get("lightningLayers")
            self._lightning_layers = (
                clone_layer_records(lightning_layers)
                if lightning_layers
                else clone_layer_records(template.get("lightningLayers"))
            )
        else:
            self._template_draft = persisted_draft
            self._template_name_draft = self._workspace.template_name
            self._spectrum_layers = clone_layer_records(template.get("layers"))
            self._lightning_layers = clone_layer_records(template.get("lightningLayers"))
""",
        "hydrate snapshot",
    )

# clamp selected lightning index near spectrum clamp
if "len(self._lightning_layers)" not in text[text.find("layer_count = len(self._spectrum_layers)"): text.find("layer_count = len(self._spectrum_layers)") + 400]:
    must_replace(
        """        layer_count = len(self._spectrum_layers)
        self._selected_spectrum_layer_index = 0 if layer_count == 0 else min(
            self._selected_spectrum_layer_index,
""",
        """        layer_count = len(self._spectrum_layers)
        lightning_count = len(self._lightning_layers)
        self._selected_lightning_layer_index = 0 if lightning_count == 0 else min(
            self._selected_lightning_layer_index,
            lightning_count - 1,
        )
        self._selected_spectrum_layer_index = 0 if layer_count == 0 else min(
            self._selected_spectrum_layer_index,
""",
        "clamp selected spectrum",
    )

# persist snapshot
if "lightning_layers=" not in text[text.find("_persist_local_draft_snapshot"): text.find("_persist_local_draft_snapshot") + 500]:
    must_replace(
        """        write_video_workspace_draft_snapshot(
            template_id,
            template_name=self._template_name_draft,
            draft=self._template_draft,
            layers=self._spectrum_layers,
        )
""",
        """        write_video_workspace_draft_snapshot(
            template_id,
            template_name=self._template_name_draft,
            draft=self._template_draft,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
        )
""",
        "persist draft snapshot",
    )

# update preview modes + renderer
if "lightning_layers=self._lightning_layers" not in text[text.find("def _update_preview"): text.find("def _update_preview") + 900]:
    must_replace(
        """        renderer_template = self._template_normalizer.to_renderer_dict(
            base=dict(self._workspace.template),
            draft=self._template_draft,
            layers=self._spectrum_layers,
            workspace={
                "logoPath": self._workspace.logo_path,
                "trackPaths": track_paths,
                "selectedMp3Path": active_track,
                "pipelineAlbum": str(
                    self._settings.get("lastAlbumName") or self._settings.get("album") or ""
                ),
            },
            track_paths=track_paths,
            active_track_path=active_track or None,
        )
        aspect = self._workspace.preview_aspect_ratio
        background_edit, spectrum_position_edit, text_domain_edit = resolve_preview_edit_modes(
            self._active_domain_tab,
            self._active_side_tab,
            edit_focus=self._preview_edit_focus,
        )
        self._stage.set_preview_edit_modes(
            background=background_edit,
            spectrum_position=spectrum_position_edit,
            text_domain=text_domain_edit,
        )
""",
        """        renderer_template = self._template_normalizer.to_renderer_dict(
            base=dict(self._workspace.template),
            draft=self._template_draft,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
            workspace={
                "logoPath": self._workspace.logo_path,
                "trackPaths": track_paths,
                "selectedMp3Path": active_track,
                "pipelineAlbum": str(
                    self._settings.get("lastAlbumName") or self._settings.get("album") or ""
                ),
            },
            track_paths=track_paths,
            active_track_path=active_track or None,
        )
        aspect = self._workspace.preview_aspect_ratio
        background_edit, spectrum_position_edit, text_domain_edit, lightning_position_edit = resolve_preview_edit_modes(
            self._active_domain_tab,
            self._active_side_tab,
            edit_focus=self._preview_edit_focus,
        )
        self._stage.set_preview_edit_modes(
            background=background_edit,
            spectrum_position=spectrum_position_edit,
            text_domain=text_domain_edit,
            lightning_position=lightning_position_edit,
        )
        self._stage.set_selected_lightning_layer_index(self._selected_lightning_layer_index)
""",
        "update preview",
    )

# spectrum position handler nearby -> lightning handler
if "def _on_preview_lightning_position_changed" not in text:
    must_replace(
        """    def _on_preview_spectrum_position_changed(self, x: int, y: int) -> None:
        if not self._template_draft:
            return
        pos_cfg = self._template_draft.get("position") if isinstance(self._template_draft.get("position"), dict) else {}
        anchor = str(pos_cfg.get("anchor") or self._template_draft.get("anchor") or "center")
        self._patch_template_draft({"anchor": anchor, "positionX": int(x), "positionY": int(y)})

    def _on_preview_text_domain_position_changed(self, domain: str, x: float, y: float) -> None:
""",
        """    def _on_preview_spectrum_position_changed(self, x: int, y: int) -> None:
        if not self._template_draft:
            return
        pos_cfg = self._template_draft.get("position") if isinstance(self._template_draft.get("position"), dict) else {}
        anchor = str(pos_cfg.get("anchor") or self._template_draft.get("anchor") or "center")
        self._patch_template_draft({"anchor": anchor, "positionX": int(x), "positionY": int(y)})

    def _on_preview_lightning_position_changed(self, x: int, y: int) -> None:
        if not self._lightning_layers:
            return
        index = max(0, min(self._selected_lightning_layer_index, len(self._lightning_layers) - 1))
        self._patch_selected_lightning_layer({"x": float(x), "y": float(y)})
        self._selected_lightning_layer_index = index

    def _on_preview_text_domain_position_changed(self, domain: str, x: float, y: float) -> None:
""",
        "spectrum position handler",
    )

# dirty state
if "lightning_dirty=" not in text:
    must_replace(
        """        dirty_map = build_draft_dirty_state(
            self._template_draft,
            persisted,
            spectrum_dirty=json.dumps(self._spectrum_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("layers") if self._workspace else []), sort_keys=True),
        )
""",
        """        dirty_map = build_draft_dirty_state(
            self._template_draft,
            persisted,
            spectrum_dirty=json.dumps(self._spectrum_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("layers") if self._workspace else []), sort_keys=True),
            lightning_dirty=json.dumps(self._lightning_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("lightningLayers") if self._workspace else []), sort_keys=True),
        )
""",
        "dirty map update",
    )

# workspace dirty includes lightning
if "lightning_layers_dirty" not in text:
    must_replace(
        """        layers = clone_layer_records(self._workspace.template.get("layers") if self._workspace else [])
        layers_dirty = json.dumps(self._spectrum_layers, sort_keys=True) != json.dumps(layers, sort_keys=True)
        return name_dirty or draft_dirty or layers_dirty
""",
        """        layers = clone_layer_records(self._workspace.template.get("layers") if self._workspace else [])
        layers_dirty = json.dumps(self._spectrum_layers, sort_keys=True) != json.dumps(layers, sort_keys=True)
        lightning_layers = clone_layer_records(
            self._workspace.template.get("lightningLayers") if self._workspace else []
        )
        lightning_layers_dirty = json.dumps(self._lightning_layers, sort_keys=True) != json.dumps(
            lightning_layers, sort_keys=True
        )
        return name_dirty or draft_dirty or layers_dirty or lightning_layers_dirty
""",
        "workspace dirty",
    )

# save patch
if "lightning_layers=self._lightning_layers" not in text[text.find("def _save_template"): text.find("def _save_template") + 1200]:
    must_replace(
        """        patch = build_video_workspace_template_save_patch(
            template=dict(self._workspace.template),
            draft=self._template_draft,
            template_name=name,
            layers=self._spectrum_layers,
        )
""",
        """        patch = build_video_workspace_template_save_patch(
            template=dict(self._workspace.template),
            draft=self._template_draft,
            template_name=name,
            layers=self._spectrum_layers,
            lightning_layers=self._lightning_layers,
        )
""",
        "save patch",
    )

# CRUD methods after spectrum CRUD block
if "def _set_lightning_layers" not in text:
    must_replace(
        """    def _set_spectrum_layers(
        self,
        layers: list[dict],
        *,
        selected_index: int,
        defer_rebind: bool = False,
    ) -> None:
        self._spectrum_layers = clone_layer_records(layers)
        self._selected_spectrum_layer_index = selected_index
        self._remember_active_spectrum_preset_session()
        self._update_inspectors(defer_rebind=defer_rebind)
        self._schedule_dirty_state_update()

    def _select_spectrum_layer(self, index: int) -> None:
""",
        """    def _set_spectrum_layers(
        self,
        layers: list[dict],
        *,
        selected_index: int,
        defer_rebind: bool = False,
    ) -> None:
        self._spectrum_layers = clone_layer_records(layers)
        self._selected_spectrum_layer_index = selected_index
        self._remember_active_spectrum_preset_session()
        self._update_inspectors(defer_rebind=defer_rebind)
        self._schedule_dirty_state_update()

    def _set_lightning_layers(
        self,
        layers: list[dict],
        *,
        selected_index: int,
        defer_rebind: bool = False,
    ) -> None:
        from features.video.lib.lightning_style_registry import normalize_lightning_layers

        self._lightning_layers = normalize_lightning_layers(clone_layer_records(layers))
        self._selected_lightning_layer_index = selected_index
        self._update_inspectors(defer_rebind=defer_rebind)
        self._schedule_dirty_state_update()

    def _select_lightning_layer(self, index: int) -> None:
        self._selected_lightning_layer_index = max(0, index)
        self._stage.set_selected_lightning_layer_index(self._selected_lightning_layer_index)
        self._update_inspectors()

    def _patch_selected_lightning_layer(self, patch: dict) -> None:
        layers = clone_layer_records(self._lightning_layers)
        if not layers:
            from features.video.lib.lightning_style_registry import default_lightning_layer

            layers = [default_lightning_layer(index=1)]
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        current = layers[index] if isinstance(layers[index], dict) else {}
        next_layer = {**current, **(patch if isinstance(patch, dict) else {})}
        if isinstance(patch, dict) and isinstance(patch.get("color"), dict):
            color = current.get("color") if isinstance(current.get("color"), dict) else {}
            next_layer["color"] = {**color, **patch["color"]}
        layers[index] = next_layer
        structural = {"style", "direction", "blend", "name", "enabled"}
        defer = not any(key in patch for key in structural)
        self._set_lightning_layers(layers, selected_index=index, defer_rebind=defer)

    def _add_lightning_layer(self) -> None:
        from features.video.lib.lightning_style_registry import default_lightning_layer

        layers = clone_layer_records(self._lightning_layers)
        next_index = len(layers) + 1
        layers.append(default_lightning_layer(index=next_index))
        self._set_lightning_layers(layers, selected_index=len(layers) - 1)

    def _duplicate_lightning_layer(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        if not layers:
            self._add_lightning_layer()
            return
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        copy = dict(layers[index])
        copy["id"] = f"lightning-{len(layers) + 1}"
        copy["name"] = f"{copy.get('name', 'Bolt')} copy"
        layers.append(copy)
        self._set_lightning_layers(layers, selected_index=len(layers) - 1)

    def _delete_lightning_layer(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        if len(layers) <= 1:
            return
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        del layers[index]
        self._set_lightning_layers(layers, selected_index=max(0, index - 1))

    def _move_lightning_layer_up(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        if index <= 0:
            return
        layers[index - 1], layers[index] = layers[index], layers[index - 1]
        self._set_lightning_layers(layers, selected_index=index - 1)

    def _move_lightning_layer_down(self) -> None:
        layers = clone_layer_records(self._lightning_layers)
        index = max(0, min(self._selected_lightning_layer_index, len(layers) - 1))
        if index >= len(layers) - 1:
            return
        layers[index + 1], layers[index] = layers[index], layers[index + 1]
        self._set_lightning_layers(layers, selected_index=index + 1)

    def _select_spectrum_layer(self, index: int) -> None:
""",
        "set spectrum layers / insert lightning CRUD",
    )

# Fix other resolve_preview_edit_modes unpack sites
needle = "background_edit, spectrum_position_edit, text_domain_edit = resolve_preview_edit_modes("
if needle in text:
    text = text.replace(
        needle,
        "background_edit, spectrum_position_edit, text_domain_edit, lightning_position_edit = resolve_preview_edit_modes(",
    )
    # ensure callers that set_preview_edit_modes without lightning still work (default False)
    # but prefer including lightning when adjacent block exists without it
    text = text.replace(
        """        self._stage.set_preview_edit_modes(
            background=background_edit,
            spectrum_position=spectrum_position_edit,
            text_domain=text_domain_edit,
        )
""",
        """        self._stage.set_preview_edit_modes(
            background=background_edit,
            spectrum_position=spectrum_position_edit,
            text_domain=text_domain_edit,
            lightning_position=lightning_position_edit,
        )
""",
    )

# diagnostics dirty map if present
diag_old = """        dirty_map = build_draft_dirty_state(
            self._template_draft,
            persisted,
            spectrum_dirty=spectrum_dirty,
        )
"""
diag_new = """        dirty_map = build_draft_dirty_state(
            self._template_draft,
            persisted,
            spectrum_dirty=spectrum_dirty,
            lightning_dirty=json.dumps(self._lightning_layers, sort_keys=True)
            != json.dumps(clone_layer_records(self._workspace.template.get("lightningLayers") if self._workspace else []), sort_keys=True),
        )
"""
if diag_old in text and "lightning_dirty=json.dumps(self._lightning_layers" not in text[text.find("def _update_diagnostics_panel"): text.find("def _update_diagnostics_panel") + 900]:
    text = text.replace(diag_old, diag_new, 1)

# other to_renderer_dict call sites — add lightning_layers when layers=self._spectrum_layers present
# Keep template-only export using workspace lightningLayers via save patch default []
# For live preview helpers that use self._spectrum_layers, pass lightning too.
marker = "layers=self._spectrum_layers,"
count = text.count(marker)
# Only add where lightning_layers is not already on next lines — manual pass via regex-ish
parts = text.split(marker)
out = [parts[0]]
for part in parts[1:]:
    if part.lstrip().startswith("lightning_layers="):
        out.append(marker + part)
    else:
        out.append(marker + "\n            lightning_layers=self._lightning_layers," + part)
text = "".join(out)

# create blank preserve lightning
if "lightning = list(self._lightning_layers)" not in text:
    must_replace(
        """            draft = dict(self._template_draft)
            layers = list(self._spectrum_layers)
            self._workspace = self._store.create_blank_template(name=name, settings=self._settings)
            self._template_draft = draft
            self._spectrum_layers = layers
            self._template_name_draft = name
""",
        """            draft = dict(self._template_draft)
            layers = list(self._spectrum_layers)
            lightning = list(self._lightning_layers)
            self._workspace = self._store.create_blank_template(name=name, settings=self._settings)
            self._template_draft = draft
            self._spectrum_layers = layers
            self._lightning_layers = lightning
            self._template_name_draft = name
""",
        "save create blank preserve",
    )

if text == orig:
    raise SystemExit("no changes applied")
path.write_text(text, encoding="utf-8")
print(f"patched ok delta={len(text) - len(orig)}")
