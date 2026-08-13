def test_geometry_editor_add_delete_move_and_simplify():
    from app.floors.room_edit_service import room_edit_service
    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]
    added = room_edit_service.add_point(points, 0, {"x": 50, "y": 0})
    assert len(added) == 5
    deleted = room_edit_service.delete_point(added, 1)
    assert len(deleted) == 4
    moved = room_edit_service.move_edge(deleted, 0, 0, 5)
    assert moved[0]["y"] == 5 and moved[1]["y"] == 5
