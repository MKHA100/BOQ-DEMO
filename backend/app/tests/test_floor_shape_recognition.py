from shapely.geometry import Polygon


def test_shape_recognizer_detects_trapezium():
    from app.floors.shape_recognizer import room_shape_recognizer
    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 80, "y": 60}, {"x": 10, "y": 60}]
    result = room_shape_recognizer.recognize(Polygon([(p["x"], p["y"]) for p in points]), points)
    assert result.shape_type == "trapezium"
    assert result.corner_count == 4
