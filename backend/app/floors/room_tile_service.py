from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class RoomTile:
    index: int
    x: int
    y: int
    width: int
    height: int
    image: bytes


class RoomTileService:
    """Create adaptive overlapping crops while keeping full-plan coordinates."""

    def create(
        self,
        image_path: Path,
        *,
        target_size: int,
        overlap: float,
        maximum_tiles: int,
    ) -> list[RoomTile]:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            width, height = image.size
            if width <= target_size and height <= target_size:
                return []
            columns = max(1, math.ceil(width / target_size))
            rows = max(1, math.ceil(height / target_size))
            while columns * rows > maximum_tiles:
                target_size = int(target_size * 1.15)
                columns = max(1, math.ceil(width / target_size))
                rows = max(1, math.ceil(height / target_size))
            tile_width = min(width, math.ceil(width / columns / max(0.1, 1.0 - overlap)))
            tile_height = min(height, math.ceil(height / rows / max(0.1, 1.0 - overlap)))
            x_values = self._starts(width, tile_width, columns)
            y_values = self._starts(height, tile_height, rows)
            output: list[RoomTile] = []
            for y in y_values:
                for x in x_values:
                    crop = image.crop((x, y, min(width, x + tile_width), min(height, y + tile_height)))
                    buffer = BytesIO()
                    crop.save(buffer, format="PNG", optimize=True)
                    output.append(RoomTile(
                        index=len(output), x=x, y=y,
                        width=crop.width, height=crop.height, image=buffer.getvalue(),
                    ))
            return output

    @staticmethod
    def _starts(total: int, size: int, count: int) -> list[int]:
        if count <= 1 or size >= total:
            return [0]
        return sorted({round(index * (total - size) / (count - 1)) for index in range(count)})


room_tile_service = RoomTileService()
