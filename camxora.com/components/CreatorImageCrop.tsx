"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CreatorButton } from "./CreatorUI";
import styles from "./creator-ui.module.css";

type Kind = "avatar" | "banner";

const OUTPUT: Record<Kind, { width: number; height: number; label: string }> = {
  avatar: { width: 512, height: 512, label: "1:1" },
  banner: { width: 1500, height: 500, label: "3:1" },
};

const MIN_ZOOM = 1;
const MAX_ZOOM = 3;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function CreatorImageCrop({
  file,
  kind,
  onCancel,
  onConfirm,
}: {
  file: File;
  kind: Kind;
  onCancel: () => void;
  onConfirm: (cropped: File) => void;
}) {
  const output = OUTPUT[kind];
  const aspect = output.width / output.height;
  const [url, setUrl] = useState("");
  const [natural, setNatural] = useState<{ width: number; height: number } | null>(null);
  const [stageWidth, setStageWidth] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const imageRef = useRef<HTMLImageElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  const stageHeight = stageWidth > 0 ? stageWidth / aspect : 0;

  useEffect(() => {
    const next = URL.createObjectURL(file);
    setUrl(next);
    setNatural(null);
    setZoom(1);
    setOffset({ x: 0, y: 0 });
    setError("");
    return () => URL.revokeObjectURL(next);
  }, [file]);

  useEffect(() => {
    function measure() {
      const available = stageRef.current?.parentElement?.clientWidth ?? 0;
      const viewport = typeof window === "undefined" ? 640 : window.innerWidth;
      const width = Math.min(kind === "banner" ? 620 : 380, available || 520, viewport - 96);
      setStageWidth(Math.max(220, Math.floor(width)));
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [kind]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", onKey);
    confirmRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const coverScale = useMemo(() => {
    if (!natural || !stageWidth || !stageHeight) return 1;
    return Math.max(stageWidth / natural.width, stageHeight / natural.height);
  }, [natural, stageWidth, stageHeight]);

  const display = useMemo(() => {
    if (!natural) return { width: 0, height: 0 };
    const scale = coverScale * zoom;
    return { width: natural.width * scale, height: natural.height * scale };
  }, [natural, coverScale, zoom]);

  const bounds = useMemo(() => {
    if (!display.width) return { x: 0, y: 0 };
    return {
      x: Math.max(0, (display.width - stageWidth) / 2),
      y: Math.max(0, (display.height - stageHeight) / 2),
    };
  }, [display, stageWidth, stageHeight]);

  useEffect(() => {
    setOffset((current) => ({
      x: clamp(current.x, -bounds.x, bounds.x),
      y: clamp(current.y, -bounds.y, bounds.y),
    }));
  }, [bounds.x, bounds.y]);

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!natural) return;
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        originX: offset.x,
        originY: offset.y,
      };
    },
    [natural, offset.x, offset.y],
  );

  const onPointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const state = drag.current;
      if (!state || state.pointerId !== event.pointerId) return;
      setOffset({
        x: clamp(state.originX + (event.clientX - state.startX), -bounds.x, bounds.x),
        y: clamp(state.originY + (event.clientY - state.startY), -bounds.y, bounds.y),
      });
    },
    [bounds.x, bounds.y],
  );

  const onPointerUp = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (drag.current?.pointerId === event.pointerId) {
      drag.current = null;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    }
  }, []);

  async function confirm() {
    const image = imageRef.current;
    if (!image || !natural || !stageWidth || !stageHeight) return;
    setBusy(true);
    setError("");
    try {
      const scale = coverScale * zoom;
      const sourceX = clamp(((display.width - stageWidth) / 2 - offset.x) / scale, 0, natural.width);
      const sourceY = clamp(((display.height - stageHeight) / 2 - offset.y) / scale, 0, natural.height);
      const sourceWidth = Math.min(stageWidth / scale, natural.width - sourceX);
      const sourceHeight = Math.min(stageHeight / scale, natural.height - sourceY);

      const canvas = document.createElement("canvas");
      canvas.width = output.width;
      canvas.height = output.height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas is not available in this browser.");
      context.imageSmoothingQuality = "high";
      context.drawImage(
        image,
        sourceX,
        sourceY,
        sourceWidth,
        sourceHeight,
        0,
        0,
        output.width,
        output.height,
      );

      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.92),
      );
      if (!blob) throw new Error("Could not prepare the cropped image.");
      const base = file.name.replace(/\.[^.]+$/, "") || kind;
      onConfirm(new File([blob], `${base}-${kind}.jpg`, { type: "image/jpeg" }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not crop the image.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={styles.cropOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="creator-crop-title"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className={styles.cropDialog}>
        <div className={styles.cropHead}>
          <h2 id="creator-crop-title" className={styles.cropTitle}>
            Crop {kind}
          </h2>
          <p className={styles.cropMeta}>
            {output.width} × {output.height} px · {output.label}
          </p>
        </div>

        <div className={styles.cropStageWrap}>
          <div
            ref={stageRef}
            className={styles.cropStage}
            style={{ width: stageWidth || undefined, height: stageHeight || undefined }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {url ? (
              <img
                ref={imageRef}
                src={url}
                alt=""
                draggable={false}
                className={styles.cropImage}
                style={{
                  width: display.width || undefined,
                  height: display.height || undefined,
                  transform: `translate(-50%, -50%) translate(${offset.x}px, ${offset.y}px)`,
                }}
                onLoad={(event) =>
                  setNatural({
                    width: event.currentTarget.naturalWidth,
                    height: event.currentTarget.naturalHeight,
                  })
                }
              />
            ) : null}
            <span className={styles.cropGrid} aria-hidden="true" />
          </div>
        </div>

        <label className={styles.cropZoom}>
          <span className={styles.cropZoomLabel}>Zoom</span>
          <input
            type="range"
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.01}
            value={zoom}
            onChange={(event) => setZoom(Number(event.target.value))}
            className={styles.cropSlider}
          />
          <span className={styles.cropZoomValue}>{zoom.toFixed(2)}×</span>
        </label>

        <p className={styles.cropHint}>Drag to reposition, then save.</p>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}

        <div className={styles.cropFooter}>
          <CreatorButton type="button" variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </CreatorButton>
          <CreatorButton
            ref={confirmRef}
            type="button"
            variant="primary"
            onClick={() => void confirm()}
            disabled={busy || !natural}
          >
            {busy ? "Preparing…" : "Save crop"}
          </CreatorButton>
        </div>
      </div>
    </div>
  );
}
