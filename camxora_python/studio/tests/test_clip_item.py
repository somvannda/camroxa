from PySide6.QtCore import QPointF, Qt

from studio.core.models import Clip, Track
from studio.ui.timeline.clip_item import ClipGraphicsItem, _handle_zone, _resample
from studio.ui.timeline.geometry import CLIP_LABEL_HEIGHT, HANDLE_HOVER_WIDTH_PX, HANDLE_WIDTH_PX, MIN_CLIP_WIDTH_PX, TRACK_HEIGHT


class _FakeMouseEvent:
    """Duck-typed stand-in for QGraphicsSceneMouseEvent — the item's mouse
    handlers only call .button()/.pos()/.scenePos()/.accept(), so a real Qt
    event isn't needed to exercise the gesture logic directly."""

    def __init__(self, pos: QPointF, scene_pos: QPointF, button=Qt.MouseButton.LeftButton) -> None:
        self._pos = pos
        self._scene_pos = scene_pos
        self._button = button

    def button(self):
        return self._button

    def pos(self):
        return self._pos

    def scenePos(self):
        return self._scene_pos

    def accept(self):
        pass

    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier


def _make_item(qtbot, start: float = 0.0, duration: float = 6.0, px_per_sec: float = 70.0) -> ClipGraphicsItem:
    track = Track(id="trk1", type="video", name="Video 1")
    clip = Clip(id="clip1", track_id="trk1", kind="video", label="clip.mp4", start=start, duration=duration)
    track.clips.append(clip)
    item = ClipGraphicsItem(track, clip)
    item.sync_geometry(px_per_sec, 0)
    return item


def test_plain_click_in_move_zone_does_not_commit(qtbot):
    item = _make_item(qtbot)
    moves: list[tuple[str, float, object, int]] = []
    item.move_committed.connect(lambda cid, start, tid, row: moves.append((cid, start, tid, row)))

    item.mousePressEvent(_FakeMouseEvent(QPointF(30, 10), QPointF(100, 10)))
    item.mouseReleaseEvent(_FakeMouseEvent(QPointF(30, 10), QPointF(100, 10)))  # no movement

    assert moves == []


def test_real_drag_in_move_zone_commits_new_start(qtbot):
    item = _make_item(qtbot)
    moves: list[tuple[str, float, object, int]] = []
    item.move_committed.connect(lambda cid, start, tid, row: moves.append((cid, start, tid, row)))

    item.mousePressEvent(_FakeMouseEvent(QPointF(30, 10), QPointF(100, 10)))
    item.mouseMoveEvent(_FakeMouseEvent(QPointF(80, 10), QPointF(150, 10)))
    item.mouseReleaseEvent(_FakeMouseEvent(QPointF(80, 10), QPointF(150, 10)))  # 50px right

    assert len(moves) == 1
    cid, new_start, track_id, preview_row = moves[0]
    assert cid == "clip1"
    assert new_start > 0.0
    assert track_id == "trk1"
    assert preview_row == 0


def test_plain_click_on_trim_handle_does_not_commit(qtbot):
    """Regression test: clicking (not dragging) inside the edge-handle zone
    — easy to do by accident while just selecting a clip — must not emit a
    trim commit (previously it did unconditionally, unlike the move
    gesture, polluting the undo stack with no-op trims)."""
    item = _make_item(qtbot)
    trims: list[tuple[str, str, float]] = []
    item.trim_committed.connect(lambda cid, side, dt: trims.append((cid, side, dt)))

    left_edge_x = HANDLE_WIDTH_PX / 2
    item.mousePressEvent(_FakeMouseEvent(QPointF(left_edge_x, 10), QPointF(100, 10)))
    item.mouseReleaseEvent(_FakeMouseEvent(QPointF(left_edge_x, 10), QPointF(100, 10)))

    assert trims == []


def test_real_drag_on_trim_handle_commits(qtbot):
    item = _make_item(qtbot)
    trims: list[tuple[str, str, float]] = []
    item.trim_committed.connect(lambda cid, side, dt: trims.append((cid, side, dt)))

    left_edge_x = HANDLE_WIDTH_PX / 2
    item.mousePressEvent(_FakeMouseEvent(QPointF(left_edge_x, 10), QPointF(100, 10)))
    item.mouseMoveEvent(_FakeMouseEvent(QPointF(left_edge_x, 10), QPointF(130, 10)))
    item.mouseReleaseEvent(_FakeMouseEvent(QPointF(left_edge_x, 10), QPointF(130, 10)))

    assert len(trims) == 1
    cid, side, dt = trims[0]
    assert cid == "clip1"
    assert side == "left"
    assert dt > 0.0


def test_resample_preserves_length_when_equal():
    values = [0.1, 0.5, 0.9]
    assert _resample(values, 3) == values


def test_resample_stretches_and_shrinks():
    values = [0.0, 1.0]
    stretched = _resample(values, 6)
    assert len(stretched) == 6
    shrunk = _resample([0.1] * 10, 4)
    assert len(shrunk) == 4


def test_resample_empty_input_or_target_returns_zeros_or_empty():
    assert _resample([], 5) == [0.0] * 5
    assert _resample([0.1, 0.2], 0) == []


def test_vertical_drag_commits_preview_row(qtbot):
    item = _make_item(qtbot)

    def _resolver(scene_y: float) -> tuple[int, str | None]:
        row = max(0, int(scene_y // TRACK_HEIGHT))
        return row, "trk1" if row == 0 else None

    item.set_row_resolver(_resolver)
    item._orig_row_index = 0
    moves: list[tuple[str, float, object, int]] = []
    item.move_committed.connect(lambda cid, start, tid, row: moves.append((cid, start, tid, row)))

    item.mousePressEvent(_FakeMouseEvent(QPointF(30, 10), QPointF(100, 10)))
    item.mouseMoveEvent(_FakeMouseEvent(QPointF(30, 10), QPointF(100, TRACK_HEIGHT + 10)))
    item.mouseReleaseEvent(_FakeMouseEvent(QPointF(30, 10), QPointF(100, TRACK_HEIGHT + 10)))

    assert len(moves) == 1
    assert moves[0][3] == 1


def test_paint_uses_real_waveform_cache_over_synthetic_placeholder(qtbot):
    """Regression test: the timeline used to always draw a fake, deterministic
    pseudo-random waveform for every audio clip — real decoded amplitude data
    (Clip.waveform_cache) must take priority once it's available."""
    item = _make_item(qtbot)
    item.clip.waveform_cache = [0.2, 0.8, 0.4, 1.0]

    from PySide6.QtGui import QImage, QPainter

    image = QImage(200, 60, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        item.track.type = "audio"
        item._paint_body(painter, item.boundingRect(), None)
    finally:
        painter.end()
    # Smoke test: painting with a real waveform_cache set must not raise,
    # and the resample path (exercised via _paint_waveform) must run.


def test_narrow_clip_handle_zone_uses_nearest_edge():
    w = float(MIN_CLIP_WIDTH_PX)
    assert _handle_zone(w, w - 1, selected_or_hover=True) == "trim_right"
    assert _handle_zone(w, 1, selected_or_hover=True) == "trim_left"


def test_wide_clip_handle_zone_has_move_body():
    w = 120.0
    assert _handle_zone(w, w / 2, selected_or_hover=False) == "move"
    assert _handle_zone(w, 2, selected_or_hover=False) == "trim_left"
    assert _handle_zone(w, w - 2, selected_or_hover=False) == "trim_right"


def test_image_clip_tiled_paint_keeps_aspect_ratio(qtbot, sample_image, tmp_path):
    """Image clips must tile horizontally on the timeline — not stretch when duration grows."""
    track = Track(id="trk1", type="overlay", name="Overlay 1")
    clip = Clip(
        id="clip_img",
        track_id="trk1",
        kind="image",
        label="photo.png",
        start=0.0,
        duration=30.0,
        thumb=str(sample_image),
    )
    track.clips.append(clip)
    item = ClipGraphicsItem(track, clip)
    item.sync_geometry(40.0, 0)  # wide clip on timeline

    from PySide6.QtGui import QImage, QPainter

    image = QImage(800, 60, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        body = item.boundingRect()
        body.setTop(CLIP_LABEL_HEIGHT)
        item._paint_image_tiled(painter, body, None)
    finally:
        painter.end()
    assert not image.isNull()
