from studio.core.project_state import ProjectState
from studio.core.registries import FILTERS, TEXT_PRESETS_UI
from studio.ui.library_panel import EffectsTab, FilterItemWidget, LibraryPanel, TextPresetItemWidget, TextTab


def test_effects_tab_renders_one_swatch_per_filter(qtbot):
    tab = EffectsTab()
    qtbot.addWidget(tab)
    swatches = tab.findChildren(FilterItemWidget)
    assert len(swatches) == len(FILTERS)
    assert {s.filter_id for s in swatches} == {f.id for f in FILTERS}


def test_text_tab_renders_one_item_per_preset(qtbot):
    tab = TextTab()
    qtbot.addWidget(tab)
    items = tab.findChildren(TextPresetItemWidget)
    assert len(items) == len(TEXT_PRESETS_UI)
    assert {i.preset_id for i in items} == {p[0] for p in TEXT_PRESETS_UI}


def test_library_panel_has_top_menu_sections(qtbot):
    state = ProjectState()
    panel = LibraryPanel(state)
    qtbot.addWidget(panel)
    titles = [panel.tabs.tabText(i) for i in range(panel.tabs.count())]
    assert titles == [
        "Import",
        "Media",
        "Music",
        "Audio",
        "Text",
        "Sticker",
        "Effects",
        "Transition",
        "Caption",
        "Filter",
        "Visualizer",
    ]


def test_library_panel_forwards_media_imported_from_media_tab(qtbot, sample_audio):
    """Regression test: nothing previously listened to MediaTab.media_imported
    at all (it was emitted but never wired to anything), which is why the
    audio-prewarm hook had nowhere to attach — LibraryPanel must re-emit it
    so MainWindow can hook playback-controller prewarming to it."""
    state = ProjectState()
    panel = LibraryPanel(state)
    qtbot.addWidget(panel)

    received: list[list] = []
    panel.media_imported.connect(lambda assets: received.append(assets))

    panel.media_tab._on_files_dropped([str(sample_audio)])
    qtbot.waitUntil(lambda: len(received) == 1, timeout=10000)

    assert len(received[0]) == 1
    assert received[0][0].type == "audio"
    panel.media_tab.wait_for_import_to_finish()
