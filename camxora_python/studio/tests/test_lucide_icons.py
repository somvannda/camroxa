from studio.ui.icons.lucide_icons import lucide_pixmap


def test_lucide_pixmap_renders_non_empty_play_icon():
    px = lucide_pixmap("play", size=24, color="#ffffff")
    assert not px.isNull()
    assert px.width() == 24
    assert px.height() == 24
