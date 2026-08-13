from shapely.geometry import Polygon


def test_wall_footprint_service_returns_inner_faces():
    from app.floors.wall_footprint_service import wall_footprint_service
    footprint = Polygon([(0, 0), (100, 0), (100, 10), (0, 10)])
    prepared = {"wall_footprints": footprint}
    assert wall_footprint_service.footprints(prepared).area == 1000
    assert wall_footprint_service.inner_faces(prepared).length > 0
