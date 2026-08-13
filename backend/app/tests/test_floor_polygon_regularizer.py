def test_rectangle_noise_becomes_four_points():
    from app.floors.polygon_regularizer import polygon_regularizer
    points = [
        {"x": 0, "y": 0}, {"x": 25, "y": 0.2}, {"x": 50, "y": 0}, {"x": 100, "y": 0},
        {"x": 100, "y": 30}, {"x": 100.2, "y": 60}, {"x": 100, "y": 80},
        {"x": 50, "y": 80.1}, {"x": 0, "y": 80}, {"x": 0.1, "y": 40},
    ]
    result = polygon_regularizer.regularize(points)
    assert result["shape_type"] == "rectangle"
    assert len(result["points"]) == 4


def test_l_shape_keeps_only_required_corners():
    from app.floors.polygon_regularizer import polygon_regularizer
    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 40}, {"x": 50, "y": 40}, {"x": 50, "y": 80}, {"x": 0, "y": 80}]
    result = polygon_regularizer.regularize(points)
    assert result["shape_type"] in {"l_shape", "polygon"}
    assert len(result["points"]) <= 6
