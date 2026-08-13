from shapely.geometry import Polygon


def test_free_space_subtracts_walls_and_voids():
    from app.floors.free_space_service import free_space_service
    envelope = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    wall = Polygon([(45, 0), (55, 0), (55, 100), (45, 100)])
    void = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    result = free_space_service.calculate(envelope, wall, void)
    assert round(result.area) == 8900
