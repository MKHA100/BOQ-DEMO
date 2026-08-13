"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { Rect } from "../types";
import type { Rotation } from "../utils/coordinates";
import { normalizeRect } from "../utils/coordinates";

type Tool = "crop" | "pan";
type Handle = "nw" | "ne" | "sw" | "se" | "move" | "draw" | "pan";

type DragState = {
  handle: Handle;
  startX: number;
  startY: number;
  startScreenX: number;
  startScreenY: number;
  startRect: Rect;
  startPan: { x: number; y: number };
};

type Point = { x: number; y: number };
type PageBox = { left: number; top: number; width: number; height: number };

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 40;
const AUTO_PAN_EDGE = 72;
const AUTO_PAN_MAX_SPEED = 22;

export function CropCanvas({
  imageUrl,
  rotation,
  value,
  onChange,
  tool,
  zoom,
  pan,
  onPanChange,
  onZoomChange,
}: {
  imageUrl: string | null;
  rotation: Rotation;
  value: Rect | null;
  onChange: (rect: Rect) => void;
  tool: Tool;
  zoom: number;
  pan: Point;
  onPanChange: (pan: Point) => void;
  onZoomChange: (zoom: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Keep the decoded image in React state.  A ref alone does not cause a
  // render when a newly selected page finishes loading, which left the canvas
  // stuck in its "Loading drawing" placeholder despite the thumbnail loading.
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const pointerRef = useRef<Point | null>(null);
  const pageBoxRef = useRef<PageBox | null>(null);
  const panRef = useRef<Point>(pan);
  const zoomRef = useRef(zoom);
  const sizeRef = useRef({ width: 900, height: 640 });
  const autoPanFrameRef = useRef<number | null>(null);
  const [size, setSize] = useState({ width: 900, height: 640 });
  const [imageReady, setImageReady] = useState(false);

  useEffect(() => {
    panRef.current = pan;
  }, [pan]);

  useEffect(() => {
    zoomRef.current = zoom;
  }, [zoom]);

  useEffect(() => {
    sizeRef.current = size;
  }, [size]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(320, Math.floor(entry.contentRect.width));
      const height = Math.max(360, Math.floor(entry.contentRect.height));
      setSize({ width, height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    setImage(null);
    setImageReady(false);
    if (!imageUrl) return;
    const nextImage = new Image();
    nextImage.decoding = "async";
    nextImage.onload = () => {
      if (cancelled) return;
      setImage(nextImage);
      setImageReady(true);
    };
    nextImage.onerror = () => {
      if (!cancelled) setImageReady(false);
    };
    nextImage.src = imageUrl;
    return () => {
      cancelled = true;
    };
  }, [imageUrl]);

  const pageBox = useMemo<PageBox | null>(() => {
    if (!imageReady || !image) return null;
    const rotated = rotation === 90 || rotation === 270;
    const sourceWidth = rotated ? image.naturalHeight : image.naturalWidth;
    const sourceHeight = rotated ? image.naturalWidth : image.naturalHeight;
    const fit = Math.min((size.width - 48) / sourceWidth, (size.height - 48) / sourceHeight);
    const scale = Math.max(0.05, fit * zoom);
    const width = sourceWidth * scale;
    const height = sourceHeight * scale;
    return {
      left: size.width / 2 - width / 2 + pan.x,
      top: size.height / 2 - height / 2 + pan.y,
      width,
      height,
    };
  }, [image, imageReady, pan.x, pan.y, rotation, size.height, size.width, zoom]);

  useEffect(() => {
    pageBoxRef.current = pageBox;
  }, [pageBox]);

  const shiftPageBox = useCallback((dx: number, dy: number) => {
    const box = pageBoxRef.current;
    if (!box) return;
    pageBoxRef.current = {
      ...box,
      left: box.left + dx,
      top: box.top + dy,
    };
  }, []);

  const setPanValue = useCallback(
    (nextPan: Point) => {
      const current = panRef.current;
      shiftPageBox(nextPan.x - current.x, nextPan.y - current.y);
      panRef.current = nextPan;
      onPanChange(nextPan);
    },
    [onPanChange, shiftPageBox]
  );

  const setZoomValue = useCallback(
    (nextZoom: number) => {
      const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom));
      zoomRef.current = clamped;
      onZoomChange(clamped);
    },
    [onZoomChange]
  );

  const zoomAtPoint = useCallback(
    (screenX: number, screenY: number, nextZoom: number) => {
      const currentZoom = zoomRef.current;
      const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom));
      const box = pageBoxRef.current;
      if (!box || currentZoom <= 0 || Math.abs(clamped - currentZoom) < 0.0001) {
        setZoomValue(clamped);
        return;
      }

      const insidePage =
        screenX >= box.left &&
        screenX <= box.left + box.width &&
        screenY >= box.top &&
        screenY <= box.top + box.height;
      const anchorX = insidePage ? (screenX - box.left) / box.width : 0.5;
      const anchorY = insidePage ? (screenY - box.top) / box.height : 0.5;
      const ratio = clamped / currentZoom;
      const nextWidth = box.width * ratio;
      const nextHeight = box.height * ratio;
      const nextLeft = screenX - anchorX * nextWidth;
      const nextTop = screenY - anchorY * nextHeight;
      const nextPan = {
        x: nextLeft - (sizeRef.current.width / 2 - nextWidth / 2),
        y: nextTop - (sizeRef.current.height / 2 - nextHeight / 2),
      };

      pageBoxRef.current = {
        left: nextLeft,
        top: nextTop,
        width: nextWidth,
        height: nextHeight,
      };
      panRef.current = nextPan;
      zoomRef.current = clamped;
      onPanChange(nextPan);
      onZoomChange(clamped);
    },
    [onPanChange, onZoomChange, setZoomValue]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      const bounds = canvas.getBoundingClientRect();
      const screenX = event.clientX - bounds.left;
      const screenY = event.clientY - bounds.top;

      if (event.ctrlKey || event.metaKey) {
        const factor = Math.exp(-event.deltaY * 0.0025);
        zoomAtPoint(screenX, screenY, zoomRef.current * factor);
        return;
      }

      const lineScale = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16 : event.deltaMode === WheelEvent.DOM_DELTA_PAGE ? sizeRef.current.height : 1;
      let deltaX = event.deltaX * lineScale;
      let deltaY = event.deltaY * lineScale;
      if (event.shiftKey && Math.abs(deltaX) < Math.abs(deltaY)) {
        deltaX = deltaY;
        deltaY = 0;
      }
      setPanValue({
        x: panRef.current.x - deltaX,
        y: panRef.current.y - deltaY,
      });
    };

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [setPanValue, zoomAtPoint]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(size.width * ratio);
    canvas.height = Math.floor(size.height * ratio);
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, size.width, size.height);
    context.fillStyle = "#eef2f7";
    context.fillRect(0, 0, size.width, size.height);

    if (!image || !pageBox) {
      context.fillStyle = "#64748b";
      context.font = "500 14px system-ui";
      context.textAlign = "center";
      context.fillText(imageUrl ? "Loading drawing" : "Select a page", size.width / 2, size.height / 2);
      return;
    }

    context.save();
    context.shadowColor = "rgba(15, 23, 42, 0.16)";
    context.shadowBlur = 18;
    context.fillStyle = "white";
    context.fillRect(pageBox.left, pageBox.top, pageBox.width, pageBox.height);
    context.restore();

    const centerX = pageBox.left + pageBox.width / 2;
    const centerY = pageBox.top + pageBox.height / 2;
    const rotated = rotation === 90 || rotation === 270;
    const drawnWidth = rotated ? pageBox.height : pageBox.width;
    const drawnHeight = rotated ? pageBox.width : pageBox.height;
    context.save();
    context.translate(centerX, centerY);
    context.rotate((rotation * Math.PI) / 180);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(image, -drawnWidth / 2, -drawnHeight / 2, drawnWidth, drawnHeight);
    context.restore();

    if (!value) return;
    const crop = {
      x: pageBox.left + value.x * pageBox.width,
      y: pageBox.top + value.y * pageBox.height,
      width: value.width * pageBox.width,
      height: value.height * pageBox.height,
    };
    context.save();
    context.fillStyle = "rgba(15, 23, 42, 0.28)";
    context.beginPath();
    context.rect(pageBox.left, pageBox.top, pageBox.width, pageBox.height);
    context.rect(crop.x, crop.y, crop.width, crop.height);
    context.fill("evenodd");
    context.strokeStyle = "#2563eb";
    context.lineWidth = 1.5;
    context.setLineDash([]);
    context.strokeRect(crop.x, crop.y, crop.width, crop.height);
    const handles = [
      [crop.x, crop.y],
      [crop.x + crop.width, crop.y],
      [crop.x, crop.y + crop.height],
      [crop.x + crop.width, crop.y + crop.height],
    ];
    for (const [x, y] of handles) {
      context.fillStyle = "white";
      context.strokeStyle = "#2563eb";
      context.lineWidth = 1.5;
      context.beginPath();
      context.rect(x - 5, y - 5, 10, 10);
      context.fill();
      context.stroke();
    }
    context.restore();
  }, [image, imageUrl, pageBox, rotation, size.height, size.width, value]);

  useEffect(() => {
    draw();
  }, [draw]);

  function screenPoint(event: ReactPointerEvent<HTMLCanvasElement>): Point {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  }

  function pagePoint(screenX: number, screenY: number, box: PageBox | null = pageBoxRef.current): Point | null {
    if (!box) return null;
    return {
      x: (screenX - box.left) / box.width,
      y: (screenY - box.top) / box.height,
    };
  }

  function identifyHandle(screenX: number, screenY: number): Handle {
    const box = pageBoxRef.current;
    if (tool === "pan" || !box) return "pan";
    if (!value) return "draw";
    const crop = {
      left: box.left + value.x * box.width,
      top: box.top + value.y * box.height,
      right: box.left + (value.x + value.width) * box.width,
      bottom: box.top + (value.y + value.height) * box.height,
    };
    const radius = 13;
    const near = (x: number, y: number) => Math.abs(screenX - x) <= radius && Math.abs(screenY - y) <= radius;
    if (near(crop.left, crop.top)) return "nw";
    if (near(crop.right, crop.top)) return "ne";
    if (near(crop.left, crop.bottom)) return "sw";
    if (near(crop.right, crop.bottom)) return "se";
    if (screenX >= crop.left && screenX <= crop.right && screenY >= crop.top && screenY <= crop.bottom) return "move";
    return "draw";
  }

  const updateCropFromPointer = useCallback(
    (screen: Point, box: PageBox | null = pageBoxRef.current) => {
      const drag = dragRef.current;
      if (!drag || drag.handle === "pan") return;
      const normalized = pagePoint(screen.x, screen.y, box);
      if (!normalized) return;
      const dx = normalized.x - drag.startX;
      const dy = normalized.y - drag.startY;
      let next = { ...drag.startRect };

      if (drag.handle === "move") {
        next.x = drag.startRect.x + dx;
        next.y = drag.startRect.y + dy;
      } else if (drag.handle === "draw") {
        next = {
          x: Math.min(drag.startX, normalized.x),
          y: Math.min(drag.startY, normalized.y),
          width: Math.abs(normalized.x - drag.startX),
          height: Math.abs(normalized.y - drag.startY),
        };
      } else {
        if (drag.handle.includes("w")) {
          next.x = drag.startRect.x + dx;
          next.width = drag.startRect.width - dx;
        }
        if (drag.handle.includes("e")) next.width = drag.startRect.width + dx;
        if (drag.handle.includes("n")) {
          next.y = drag.startRect.y + dy;
          next.height = drag.startRect.height - dy;
        }
        if (drag.handle.includes("s")) next.height = drag.startRect.height + dy;
      }

      if (next.width < 0) {
        next.x += next.width;
        next.width = Math.abs(next.width);
      }
      if (next.height < 0) {
        next.y += next.height;
        next.height = Math.abs(next.height);
      }
      next.width = Math.max(0.005, Math.min(next.width, 1));
      next.height = Math.max(0.005, Math.min(next.height, 1));
      next.x = Math.min(Math.max(next.x, 0), 1 - next.width);
      next.y = Math.min(Math.max(next.y, 0), 1 - next.height);
      onChange(next);
    },
    [onChange]
  );

  const stopAutoPan = useCallback(() => {
    if (autoPanFrameRef.current !== null) {
      window.cancelAnimationFrame(autoPanFrameRef.current);
      autoPanFrameRef.current = null;
    }
  }, []);

  const autoPanSpeed = useCallback((position: number, extent: number) => {
    if (position < AUTO_PAN_EDGE) {
      return AUTO_PAN_MAX_SPEED * Math.min(1, (AUTO_PAN_EDGE - position) / AUTO_PAN_EDGE);
    }
    if (position > extent - AUTO_PAN_EDGE) {
      return -AUTO_PAN_MAX_SPEED * Math.min(1, (position - (extent - AUTO_PAN_EDGE)) / AUTO_PAN_EDGE);
    }
    return 0;
  }, []);

  const startAutoPan = useCallback(() => {
    stopAutoPan();
    const tick = () => {
      const drag = dragRef.current;
      const pointer = pointerRef.current;
      const box = pageBoxRef.current;
      if (!drag || drag.handle === "pan" || !pointer || !box) {
        autoPanFrameRef.current = null;
        return;
      }

      const dx = autoPanSpeed(pointer.x, sizeRef.current.width);
      const dy = autoPanSpeed(pointer.y, sizeRef.current.height);
      if (dx !== 0 || dy !== 0) {
        const nextPan = {
          x: panRef.current.x + dx,
          y: panRef.current.y + dy,
        };
        setPanValue(nextPan);
        updateCropFromPointer(pointer, pageBoxRef.current);
      }
      autoPanFrameRef.current = window.requestAnimationFrame(tick);
    };
    autoPanFrameRef.current = window.requestAnimationFrame(tick);
  }, [autoPanSpeed, setPanValue, stopAutoPan, updateCropFromPointer]);

  useEffect(() => stopAutoPan, [stopAutoPan]);

  function pointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    const box = pageBoxRef.current;
    if (!box) return;
    event.preventDefault();
    const screen = screenPoint(event);
    const forcePan = event.button === 1 || event.button === 2 || tool === "pan";
    const handle = forcePan ? "pan" : identifyHandle(screen.x, screen.y);
    const normalized = pagePoint(screen.x, screen.y, box);
    if (handle !== "pan" && !normalized) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    const startRect = value ?? normalizeRect({
      x: normalized?.x ?? 0,
      y: normalized?.y ?? 0,
      width: 0.005,
      height: 0.005,
    });
    dragRef.current = {
      handle,
      startX: normalized?.x ?? 0,
      startY: normalized?.y ?? 0,
      startScreenX: screen.x,
      startScreenY: screen.y,
      startRect,
      startPan: panRef.current,
    };
    pointerRef.current = screen;
    if (handle === "draw") onChange(startRect);
    if (handle !== "pan") startAutoPan();
  }

  function pointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const screen = screenPoint(event);
    pointerRef.current = screen;

    if (drag.handle === "pan") {
      const nextPan = {
        x: drag.startPan.x + screen.x - drag.startScreenX,
        y: drag.startPan.y + screen.y - drag.startScreenY,
      };
      setPanValue(nextPan);
      return;
    }
    updateCropFromPointer(screen);
  }

  function pointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    dragRef.current = null;
    pointerRef.current = null;
    stopAutoPan();
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <div ref={containerRef} className="relative h-full min-h-[430px] w-full overflow-hidden overscroll-none bg-slate-100">
      <canvas
        ref={canvasRef}
        tabIndex={0}
        aria-label="Floor plan crop canvas"
        className={tool === "pan" ? "block cursor-grab touch-none select-none active:cursor-grabbing" : "block cursor-crosshair touch-none select-none"}
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerUp}
        onPointerCancel={pointerUp}
        onContextMenu={(event) => event.preventDefault()}
      />
      {!imageUrl ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm font-medium text-slate-500">
          Select a source page to begin.
        </div>
      ) : null}
      {imageUrl ? (
        <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-slate-950/75 px-3 py-1.5 text-[11px] font-medium text-white shadow-sm">
          Ctrl + wheel to zoom · Wheel to move · Drag near an edge to continue the crop
        </div>
      ) : null}
    </div>
  );
}
