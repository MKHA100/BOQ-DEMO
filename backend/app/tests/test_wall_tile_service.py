from __future__ import annotations

from io import BytesIO


def test_wall_tiles_preserve_original_colour_and_limit_requests(tmp_path):
    from PIL import Image

    from app.model_review.wall_tile_service import wall_tile_service

    image = Image.new("RGB", (800, 600), (25, 120, 210))
    path = tmp_path / "plan.png"
    image.save(path)

    tiles = wall_tile_service.tiles(
        path,
        target_pixels=400,
        overlap=0.25,
        maximum_tiles=6,
    )

    assert 1 < len(tiles) <= 6
    with Image.open(BytesIO(tiles[0].content)) as tile:
        assert tile.convert("RGB").getpixel((10, 10)) == (25, 120, 210)
