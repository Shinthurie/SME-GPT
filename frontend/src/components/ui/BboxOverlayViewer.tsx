"use client";

/**
 * Iteration 10 — Bbox Overlay Viewer.
 *
 * Renders a document image with SVG bounding-box rectangles drawn over it,
 * one per SpatialChunk from `spatialChunksJson`.  The SVG uses the same
 * aspect-ratio logic as CSS `object-fit: contain` so rectangles align with
 * the image content regardless of the container size.
 *
 * Graceful degradation: if `spatialChunksJson` is null / unparseable, the
 * component falls back to a plain `<img>`.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

type Provenance = {
  page: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2] in original px
};

type SpatialChunk = {
  chunk_id: string;
  chunk_type: string;
  text: string;
  provenance: Provenance;
};

type SpatialChunksDoc = {
  tenant_id: string;
  document_id: string;
  pages: Array<{ page: number; chunks: SpatialChunk[] }>;
};

export type BboxOverlayViewerProps = {
  imageUrl: string;
  documentId: string;
  spatialChunksJson?: string | null;
  activeChunkId?: string | null;
  onChunkSelect?: (chunkId: string | null) => void;
};

// ── Colour map ────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  header:          "#2563ff",  // blue
  line_item_row:   "#16a34a",  // green
  line_item_block: "#16a34a",
  key_value:       "#ea580c",  // orange
  section_text:    "#7c3aed",  // purple
  // simpler schema fallbacks
  Header:   "#2563ff",
  KeyValue: "#ea580c",
  LineItem: "#16a34a",
  Text:     "#94a3b8",
};

function chunkColor(type: string): string {
  return TYPE_COLORS[type] ?? "#94a3b8";
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function BboxOverlayViewer({
  imageUrl,
  documentId,
  spatialChunksJson,
  activeChunkId,
  onChunkSelect,
}: BboxOverlayViewerProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);
  const [showOverlay, setShowOverlay] = useState(true);
  const [chunks, setChunks] = useState<SpatialChunk[]>([]);
  // Zoom for small/tall documents (e.g. an A4 PDF page shrinks to unreadable at
  // fit-width). 1 = fit width; higher enlarges and the viewport scrolls to pan.
  const [zoom, setZoom] = useState(1);
  const ZOOM_MIN = 1, ZOOM_MAX = 5, ZOOM_STEP = 0.5;
  useEffect(() => { setZoom(1); }, [imageUrl]);

  // Parse spatial chunks once
  useEffect(() => {
    if (!spatialChunksJson) {
      setChunks([]);
      return;
    }
    try {
      const doc = JSON.parse(spatialChunksJson) as SpatialChunksDoc;
      // Collect all chunks across all pages (we show page 1 image, so filter page 1)
      const all: SpatialChunk[] = [];
      for (const pg of doc.pages ?? []) {
        for (const ch of pg.chunks ?? []) {
          if (ch.provenance?.bbox) all.push(ch);
        }
      }
      setChunks(all);
    } catch {
      setChunks([]);
    }
  }, [spatialChunksJson]);

  const handleImgLoad = useCallback(() => {
    const img = imgRef.current;
    if (img) setImgSize({ w: img.naturalWidth, h: img.naturalHeight });
  }, []);

  const hasOverlay = chunks.length > 0 && imgSize;

  return (
    <div
      className="relative overflow-hidden rounded-[16px]"
      style={{ background: "var(--surface-2)" }}
    >
      {/* Scroll/pan viewport. The inner wrapper is sized to zoom * 100% of the
          viewport width; at zoom 1 a tall page overflows vertically (so it
          scrolls) and zooming in overflows both axes (so you can pan). */}
      <div className="relative h-[420px] overflow-auto rounded-[12px] sm:h-[520px]">
        <div className="relative" style={{ width: `${zoom * 100}%` }}>
          {/* Document image */}
          <img
            ref={imgRef}
            src={imageUrl}
            alt={documentId}
            onLoad={handleImgLoad}
            draggable={false}
            className="block w-full select-none rounded-[12px]"
          />

          {/* SVG overlay — sits exactly over the image (same box, same aspect) */}
          {hasOverlay && showOverlay && imgSize && (
            <svg
              viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
              preserveAspectRatio="xMidYMid meet"
              className="absolute inset-0 h-full w-full"
              style={{ pointerEvents: onChunkSelect ? "auto" : "none" }}
            >
          {chunks.map((chunk) => {
            const [x1, y1, x2, y2] = chunk.provenance.bbox;
            const isActive = chunk.chunk_id === activeChunkId;
            const color = chunkColor(chunk.chunk_type);
            return (
              <g key={chunk.chunk_id}>
                <rect
                  x={x1}
                  y={y1}
                  width={Math.max(x2 - x1, 1)}
                  height={Math.max(y2 - y1, 1)}
                  fill={isActive ? `${color}22` : "none"}
                  stroke={color}
                  strokeWidth={isActive ? 3 : 1.5}
                  strokeOpacity={isActive ? 1 : 0.65}
                  rx={2}
                  onClick={() => onChunkSelect?.(isActive ? null : chunk.chunk_id)}
                  style={{ cursor: onChunkSelect ? "pointer" : "default", pointerEvents: "all" }}
                />
                {isActive && (
                  <text
                    x={x1 + 3}
                    y={y1 - 4}
                    fontSize={11}
                    fill={color}
                    fontWeight="bold"
                  >
                    {chunk.chunk_type}
                  </text>
                )}
              </g>
            );
          })}
            </svg>
          )}
        </div>
      </div>

      {/* Zoom controls */}
      {imageUrl && (
      <div className="absolute right-2 top-2 flex flex-col gap-1.5">
        <button
          onClick={() => setZoom((z) => Math.min(+(z + ZOOM_STEP).toFixed(2), ZOOM_MAX))}
          disabled={zoom >= ZOOM_MAX}
          title="Zoom in"
          aria-label="Zoom in"
          className="flex h-9 w-9 items-center justify-center rounded-full shadow transition hover:opacity-90 disabled:opacity-40"
          style={{ background: "var(--surface)", color: "var(--text-2)" }}
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">zoom_in</span>
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(+(z - ZOOM_STEP).toFixed(2), ZOOM_MIN))}
          disabled={zoom <= ZOOM_MIN}
          title="Zoom out"
          aria-label="Zoom out"
          className="flex h-9 w-9 items-center justify-center rounded-full shadow transition hover:opacity-90 disabled:opacity-40"
          style={{ background: "var(--surface)", color: "var(--text-2)" }}
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">zoom_out</span>
        </button>
      </div>
      )}

      {/* Overlay controls */}
      {chunks.length > 0 && (
        <div className="absolute right-2 top-[7.25rem] flex flex-col gap-1.5">
          <button
            onClick={() => setShowOverlay((p) => !p)}
            title={showOverlay ? "Hide bounding boxes" : "Show bounding boxes"}
            aria-label={showOverlay ? "Hide bounding boxes" : "Show bounding boxes"}
            aria-pressed={showOverlay}
            className="flex h-9 w-9 items-center justify-center rounded-full shadow transition hover:opacity-90"
            style={{ background: "var(--surface)", color: showOverlay ? "var(--brand-mid)" : "var(--text-3)" }}
          >
            <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
              {showOverlay ? "visibility" : "visibility_off"}
            </span>
          </button>
          {showOverlay && activeChunkId && (
            <button
              onClick={() => onChunkSelect?.(null)}
              title="Clear selection"
              aria-label="Clear selection"
              className="flex h-9 w-9 items-center justify-center rounded-full shadow transition hover:opacity-90"
              style={{ background: "var(--surface)", color: "var(--text-2)" }}
            >
              <span className="material-symbols-outlined text-[20px]" aria-hidden="true">close</span>
            </button>
          )}
        </div>
      )}

      {/* Legend */}
      {hasOverlay && showOverlay && (
        <div className="absolute bottom-2 left-2 flex flex-wrap gap-1.5">
          {Object.entries({
            header: "Header",
            key_value: "Key-Value",
            line_item_row: "Line Item",
            section_text: "Text",
          }).map(([type, label]) => (
            <span
              key={type}
              className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold shadow"
              style={{ background: "var(--surface)", color: chunkColor(type) }}
            >
              <span
                className="inline-block h-2 w-2 rounded-sm border"
                style={{ borderColor: chunkColor(type) }}
              />
              {label}
            </span>
          ))}
        </div>
      )}

      {/* Fallback: no image */}
      {!imageUrl && (
        <div className="absolute inset-0 flex items-center justify-center text-[13px] text-[var(--text-3)]">
          No saved preview image for this document
        </div>
      )}
    </div>
  );
}
