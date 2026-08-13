import type { Rect } from "../types";

export type Rotation = 0 | 90 | 180 | 270;

const clamp = (value: number, minimum = 0, maximum = 1) => Math.min(maximum, Math.max(minimum, value));

export function normalizeRect(rect: Rect): Rect {
  const x = clamp(rect.x);
  const y = clamp(rect.y);
  const width = clamp(rect.width, 0.005, 1 - x);
  const height = clamp(rect.height, 0.005, 1 - y);
  return { x, y, width, height };
}

export function displayToOriginal(rect: Rect, rotation: Rotation): Rect {
  const value = normalizeRect(rect);
  if (rotation === 90) {
    return normalizeRect({
      x: value.y,
      y: 1 - value.x - value.width,
      width: value.height,
      height: value.width,
    });
  }
  if (rotation === 180) {
    return normalizeRect({
      x: 1 - value.x - value.width,
      y: 1 - value.y - value.height,
      width: value.width,
      height: value.height,
    });
  }
  if (rotation === 270) {
    return normalizeRect({
      x: 1 - value.y - value.height,
      y: value.x,
      width: value.height,
      height: value.width,
    });
  }
  return value;
}

export function originalToDisplay(rect: Rect, rotation: Rotation): Rect {
  const value = normalizeRect(rect);
  if (rotation === 90) {
    return normalizeRect({
      x: 1 - value.y - value.height,
      y: value.x,
      width: value.height,
      height: value.width,
    });
  }
  if (rotation === 180) {
    return normalizeRect({
      x: 1 - value.x - value.width,
      y: 1 - value.y - value.height,
      width: value.width,
      height: value.height,
    });
  }
  if (rotation === 270) {
    return normalizeRect({
      x: value.y,
      y: 1 - value.x - value.width,
      width: value.height,
      height: value.width,
    });
  }
  return value;
}

export function toOriginalPageRect(
  displayRect: Rect,
  rotation: Rotation,
  originalWidth: number,
  originalHeight: number
): Rect {
  const original = displayToOriginal(displayRect, rotation);
  return {
    x: original.x * originalWidth,
    y: original.y * originalHeight,
    width: original.width * originalWidth,
    height: original.height * originalHeight,
  };
}

export function fromOriginalPageRect(
  originalRect: Rect,
  rotation: Rotation,
  originalWidth: number,
  originalHeight: number
): Rect {
  return originalToDisplay(
    {
      x: originalRect.x / originalWidth,
      y: originalRect.y / originalHeight,
      width: originalRect.width / originalWidth,
      height: originalRect.height / originalHeight,
    },
    rotation
  );
}
