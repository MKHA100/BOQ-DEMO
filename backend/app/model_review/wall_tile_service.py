from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class WallRecoveryTile:
    index: int
    x: int
    y: int
    width: int
    height: int
    content: bytes


class WallTileService:
    """Create overlapping tiles from the original colour floor image."""

    def tiles(
        self,
        image_path: Path,
        *,
        target_pixels: int,
        overlap: float,
        maximum_tiles: int,
    ) -> list[WallRecoveryTile]:
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        width, height = image.size
        columns = max(1, math.ceil(width / target_pixels))
        rows = max(1, math.ceil(height / target_pixels))
        while columns * rows > maximum_tiles:
            target_pixels = max(target_pixels + 1, int(target_pixels * 1.15))
            columns = max(1, math.ceil(width / target_pixels))
            rows = max(1, math.ceil(height / target_pixels))
        tile_width = min(
            width, math.ceil(width / columns / max(0.1, 1.0 - overlap))
        )
        tile_height = min(
            height, math.ceil(height / rows / max(0.1, 1.0 - overlap))
        )
        output: list[WallRecoveryTile] = []
        for y in self._starts(height, tile_height, rows):
            for x in self._starts(width, tile_width, columns):
                crop = image.crop(
                    (x, y, min(width, x + tile_width), min(height, y + tile_height))
                )
                buffer = BytesIO()
                crop.save(buffer, format="PNG", optimize=True)
                output.append(
                    WallRecoveryTile(
                        index=len(output),
                        x=x,
                        y=y,
                        width=crop.width,
                        height=crop.height,
                        content=buffer.getvalue(),
                    )
                )
        return output

    @staticmethod
    def _starts(total: int, size: int, count: int) -> list[int]:
        if count <= 1 or size >= total:
            return [0]
        return sorted(
            {
                round(index * (total - size) / (count - 1))
                for index in range(count)
            }
        )


wall_tile_service = WallTileService()
