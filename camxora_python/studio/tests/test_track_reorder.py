from studio.core.project_state import ProjectState


def test_reorder_track_moves_in_list():
    state = ProjectState()
    a = state.add_track("video")
    b = state.add_track("audio")
    c = state.add_track("overlay")
    assert [t.id for t in state.project.tracks] == [a.id, b.id, c.id]

    state.reorder_track(c.id, 0)
    assert [t.id for t in state.project.tracks] == [c.id, a.id, b.id]

    state.reorder_track(a.id, 2)
    assert [t.id for t in state.project.tracks] == [c.id, b.id, a.id]
