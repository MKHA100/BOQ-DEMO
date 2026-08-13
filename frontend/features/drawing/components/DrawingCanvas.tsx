"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import type { Point } from "../types";

export type DrawingCanvasTool = "select" | "pan" | "point" | "draw";

type ViewState = {
  zoom: number;
  pan: Point;
};

type Props = {
  imageUrl: string | null;
  width: number;
  height: number;
  tool?: DrawingCanvasTool;
  children?: ReactNode;
  onCanvasClick?: (point: Point) => void;
  onViewChange?: (view: ViewState) => void;
  initialView?: ViewState;
  className?: string;
};

type PanDrag = {
  pointerId: number;
  startClient: Point;
  startPan: Point;
  moved: boolean;
};

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 40;
const VIEW_PADDING = 40;

export function DrawingCanvas({
  imageUrl,
  width,
  height,
  tool = "select",
  children,
  onCanvasClick,
  onViewChange,
  initialView,
  className = "",
}: Props) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const pointerRef = useRef<PanDrag | null>(null);
  const suppressClickRef = useRef(false);
  const onViewChangeRef = useRef(onViewChange);
  const reportedViewRef = useRef<ViewState | null>(null);
  const zoomRef = useRef(initialView?.zoom ?? 1);
  const panRef = useRef<Point>(initialView?.pan ?? { x: 0, y: 0 });
  const sizeRef = useRef({ width: 900, height: 620 });

  const [zoom, setZoom] = useState(initialView?.zoom ?? 1);
  const [pan, setPan] = useState<Point>(initialView?.pan ?? { x: 0, y: 0 });
  const [viewportSize, setViewportSize] = useState({ width: 900, height: 620 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  const sourceWidth = Math.max(1, width);
  const sourceHeight = Math.max(1, height);

  useEffect(() => {
    zoomRef.current = zoom;
  }, [zoom]);

  useEffect(() => {
    panRef.current = pan;
  }, [pan]);

  useEffect(() => {
    sizeRef.current = viewportSize;
  }, [viewportSize]);

  useEffect(() => {
    onViewChangeRef.current = onViewChange;
  }, [onViewChange]);

  useEffect(() => {
    if (!Number.isFinite(zoom) || !Number.isFinite(pan.x) || !Number.isFinite(pan.y)) return;
    const previous = reportedViewRef.current;
    if (
      previous
      && Math.abs(previous.zoom - zoom) < 0.0001
      && Math.abs(previous.pan.x - pan.x) < 0.0001
      && Math.abs(previous.pan.y - pan.y) < 0.0001
    ) return;
    const next = { zoom, pan: { x: pan.x, y: pan.y } };
    reportedViewRef.current = next;
    onViewChangeRef.current?.(next);
  }, [pan.x, pan.y, zoom]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(([entry]) => {
      const next = {
        width: Math.max(320, Math.floor(entry.contentRect.width)),
        height: Math.max(360, Math.floor(entry.contentRect.height)),
      };
      sizeRef.current = next;
      setViewportSize((current) => current.width === next.width && current.height === next.height ? current : next);
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const onFullscreenChange = () => setIsFullscreen(document.fullscreenElement === viewportRef.current);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  useEffect(() => {
    const nextZoom = initialView?.zoom ?? 1;
    const nextPan = initialView?.pan ?? { x: 0, y: 0 };
    zoomRef.current = nextZoom;
    panRef.current = nextPan;
    setZoom((current) => Math.abs(current - nextZoom) < 0.0001 ? current : nextZoom);
    setPan((current) => current.x === nextPan.x && current.y === nextPan.y ? current : nextPan);
  }, [height, imageUrl, initialView?.pan?.x, initialView?.pan?.y, initialView?.zoom, width]);

  const fitScale = useMemo(() => {
    const availableWidth = Math.max(1, viewportSize.width - VIEW_PADDING * 2);
    const availableHeight = Math.max(1, viewportSize.height - VIEW_PADDING * 2);
    return Math.max(0.0001, Math.min(availableWidth / sourceWidth, availableHeight / sourceHeight));
  }, [sourceHeight, sourceWidth, viewportSize.height, viewportSize.width]);

  const pageWidth = sourceWidth * fitScale * zoom;
  const pageHeight = sourceHeight * fitScale * zoom;
  const pageLeft = (viewportSize.width - pageWidth) / 2 + pan.x;
  const pageTop = (viewportSize.height - pageHeight) / 2 + pan.y;

  const updatePan = useCallback((next: Point) => {
    panRef.current = next;
    setPan(next);
  }, []);

  const updateZoom = useCallback((next: number) => {
    const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
    zoomRef.current = clamped;
    setZoom(clamped);
  }, []);

  const layoutFor = useCallback((viewZoom: number, viewPan: Point) => {
    const viewport = sizeRef.current;
    const availableWidth = Math.max(1, viewport.width - VIEW_PADDING * 2);
    const availableHeight = Math.max(1, viewport.height - VIEW_PADDING * 2);
    const baseScale = Math.max(0.0001, Math.min(availableWidth / sourceWidth, availableHeight / sourceHeight));
    const renderedWidth = sourceWidth * baseScale * viewZoom;
    const renderedHeight = sourceHeight * baseScale * viewZoom;
    return {
      fitScale: baseScale,
      width: renderedWidth,
      height: renderedHeight,
      left: (viewport.width - renderedWidth) / 2 + viewPan.x,
      top: (viewport.height - renderedHeight) / 2 + viewPan.y,
    };
  }, [sourceHeight, sourceWidth]);

  const zoomAtPoint = useCallback((viewportX: number, viewportY: number, requestedZoom: number) => {
    const currentZoom = zoomRef.current;
    const nextZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, requestedZoom));
    if (Math.abs(nextZoom - currentZoom) < 0.0001) return;

    const currentPan = panRef.current;
    const currentLayout = layoutFor(currentZoom, currentPan);
    const sourceX = (viewportX - currentLayout.left) / Math.max(1, currentLayout.width);
    const sourceY = (viewportY - currentLayout.top) / Math.max(1, currentLayout.height);
    const nextLayout = layoutFor(nextZoom, { x: 0, y: 0 });
    const nextPan = {
      x: viewportX - sourceX * nextLayout.width - nextLayout.left,
      y: viewportY - sourceY * nextLayout.height - nextLayout.top,
    };

    panRef.current = nextPan;
    zoomRef.current = nextZoom;
    setPan(nextPan);
    setZoom(nextZoom);
  }, [layoutFor]);

  const fit = useCallback(() => {
    zoomRef.current = 1;
    panRef.current = { x: 0, y: 0 };
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();

      const bounds = viewport.getBoundingClientRect();
      const pointerX = event.clientX - bounds.left;
      const pointerY = event.clientY - bounds.top;

      if (event.ctrlKey || event.metaKey) {
        const factor = Math.exp(-event.deltaY * 0.0025);
        zoomAtPoint(pointerX, pointerY, zoomRef.current * factor);
        return;
      }

      const unit = event.deltaMode === WheelEvent.DOM_DELTA_LINE
        ? 16
        : event.deltaMode === WheelEvent.DOM_DELTA_PAGE
          ? sizeRef.current.height
          : 1;
      let deltaX = event.deltaX * unit;
      let deltaY = event.deltaY * unit;
      if (event.shiftKey && Math.abs(deltaX) < Math.abs(deltaY)) {
        deltaX = deltaY;
        deltaY = 0;
      }
      updatePan({
        x: panRef.current.x - deltaX,
        y: panRef.current.y - deltaY,
      });
    };

    viewport.addEventListener("wheel", handleWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", handleWheel);
  }, [updatePan, zoomAtPoint]);

  const toSourcePoint = useCallback((clientX: number, clientY: number): Point | null => {
    const viewport = viewportRef.current;
    if (!viewport || !imageUrl) return null;
    const bounds = viewport.getBoundingClientRect();
    const layout = layoutFor(zoomRef.current, panRef.current);
    const x = ((clientX - bounds.left - layout.left) / Math.max(1, layout.width)) * sourceWidth;
    const y = ((clientY - bounds.top - layout.top) / Math.max(1, layout.height)) * sourceHeight;
    if (x < 0 || y < 0 || x > sourceWidth || y > sourceHeight) return null;
    return { x, y };
  }, [imageUrl, layoutFor, sourceHeight, sourceWidth]);

  function pointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    const forcePan = tool === "pan" || event.button === 1 || event.button === 2;
    if (!forcePan) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    pointerRef.current = {
      pointerId: event.pointerId,
      startClient: { x: event.clientX, y: event.clientY },
      startPan: { ...panRef.current },
      moved: false,
    };
  }

  function pointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = pointerRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startClient.x;
    const dy = event.clientY - drag.startClient.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
    updatePan({ x: drag.startPan.x + dx, y: drag.startPan.y + dy });
  }

  function pointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = pointerRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    suppressClickRef.current = drag.moved;
    pointerRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function canvasClick(event: ReactMouseEvent<SVGSVGElement>) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    if (tool === "pan" || !onCanvasClick) return;
    const point = toSourcePoint(event.clientX, event.clientY);
    if (point) onCanvasClick(point);
  }

  function doubleClick(event: ReactMouseEvent<HTMLDivElement>) {
    if (!imageUrl) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    zoomAtPoint(event.clientX - bounds.left, event.clientY - bounds.top, zoomRef.current * 1.6);
  }

  function keyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const centerX = sizeRef.current.width / 2;
    const centerY = sizeRef.current.height / 2;
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      zoomAtPoint(centerX, centerY, zoomRef.current * 1.25);
    } else if (event.key === "-") {
      event.preventDefault();
      zoomAtPoint(centerX, centerY, zoomRef.current / 1.25);
    } else if (event.key === "0") {
      event.preventDefault();
      fit();
    }
  }

  async function toggleFullscreen() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (document.fullscreenElement === viewport) {
      await document.exitFullscreen();
      return;
    }
    await viewport.requestFullscreen();
  }

  const cursorClass = tool === "pan"
    ? "cursor-grab active:cursor-grabbing"
    : tool === "point" || tool === "draw"
      ? "cursor-crosshair"
      : "cursor-default";

  return (
    <div
      ref={viewportRef}
      tabIndex={0}
      aria-label="Drawing viewer"
      className={`relative h-full min-h-0 w-full overflow-hidden overscroll-none bg-slate-100 outline-none ${cursorClass} ${isFullscreen ? "bg-slate-200" : ""} ${className}`}
      style={{ touchAction: "none", overscrollBehavior: "contain" }}
      onPointerDown={pointerDown}
      onPointerMove={pointerMove}
      onPointerUp={pointerUp}
      onPointerCancel={pointerUp}
      onContextMenu={(event) => event.preventDefault()}
      onDoubleClick={doubleClick}
      onKeyDown={keyDown}
    >
      <div className="absolute right-4 top-4 z-30 flex items-center gap-1 rounded-xl border border-slate-200 bg-white/95 p-1 shadow-sm backdrop-blur">
        <button type="button" className="h-9 rounded-lg px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50" onClick={() => zoomAtPoint(viewportSize.width / 2, viewportSize.height / 2, zoomRef.current / 1.25)} aria-label="Zoom out">−</button>
        <span className="min-w-14 text-center text-xs font-semibold text-slate-500">{Math.round(zoom * 100)}%</span>
        <button type="button" className="h-9 rounded-lg px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50" onClick={() => zoomAtPoint(viewportSize.width / 2, viewportSize.height / 2, zoomRef.current * 1.25)} aria-label="Zoom in">+</button>
        <button type="button" className="h-9 rounded-lg px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50" onClick={fit}>Fit</button>
        <button type="button" className="h-9 rounded-lg px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50" onClick={() => void toggleFullscreen()}>{isFullscreen ? "Exit full screen" : "Full screen"}</button>
      </div>

      {imageUrl ? (
        <svg
          viewBox={`0 0 ${sourceWidth} ${sourceHeight}`}
          preserveAspectRatio="none"
          className="absolute select-none bg-white shadow-xl"
          style={{
            left: pageLeft,
            top: pageTop,
            width: pageWidth,
            height: pageHeight,
          }}
          onClick={canvasClick}
        >
          <image href={imageUrl} x={0} y={0} width={sourceWidth} height={sourceHeight} preserveAspectRatio="none" />
          {children}
        </svg>
      ) : (
        <div className="flex h-full items-center justify-center text-sm text-slate-500">Drawing preview is not ready.</div>
      )}

      {imageUrl ? (
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-20 -translate-x-1/2 rounded-full bg-slate-950/75 px-3 py-1.5 text-[11px] font-medium text-white shadow-sm">
          Ctrl + wheel to zoom · Wheel to move · Middle-drag to move · Double-click to zoom
        </div>
      ) : null}
    </div>
  );
}
