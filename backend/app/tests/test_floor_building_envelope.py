from shapely.geometry import Polygon
from shapely.ops import unary_union


def test_building_envelope_uses_wall_footprints():
    from app.floors.building_envelope_service import building_envelope_service
    footprints = Polygon([(10, 10), (90, 10), (90, 90), (10, 90)]).boundary.buffer(3)
    envelope = building_envelope_service.build({"wall_footprints": footprints, "typical_thickness_px": 6}, 200, 200)
    assert not envelope.is_empty
    assert envelope.area < 200 * 200


def test_building_envelope_keeps_disconnected_wall_groups():
    from app.floors.building_envelope_service import building_envelope_service

    left = Polygon([(10, 10), (70, 10), (70, 80), (10, 80)]).boundary.buffer(2)
    right = Polygon([(130, 110), (190, 110), (190, 190), (130, 190)]).boundary.buffer(2)
    envelope = building_envelope_service.build(
        {"wall_footprints": unary_union([left, right]), "typical_thickness_px": 4},
        220,
        220,
    )

    assert envelope.contains(left.centroid)
    assert envelope.contains(right.centroid)
