import { useCallback, useEffect, useRef, useState } from "react";
import type { VizzyState } from "../../../electron/shared/types";

const EMPTY_STATE: VizzyState = {
  attached: false,
  ready: false,
  crashed: false,
  projectName: "",
  dirty: false,
  nodeCount: 0,
  fftTier: "unknown",
  crossOriginIsolated: false,
  path: null,
  error: null,
};

function boundsOf(element: HTMLElement) {
  const rect = element.getBoundingClientRect();
  return {
    x: rect.left,
    y: rect.top,
    width: rect.width,
    height: rect.height,
  };
}

export interface VizzyHostHandle {
  state: VizzyState;
  busy: "save" | "open" | "attach" | null;
  closed: boolean;
  containerRef: React.RefObject<HTMLDivElement | null>;
  save: () => Promise<void>;
  open: () => Promise<void>;
  reload: () => Promise<void>;
  closeEditor: () => void;
  openEditor: () => void;
}

/**
 * Owns the `WebContentsView` placement for the Vizzy page:
 *  - attaches the native view to this page's rectangle,
 *  - forwards bounds on resize/layout shifts,
 *  - detaches (and stops the editor process) on unmount,
 *  - mirrors the state the editor reports back into the shell strip.
 */
export function useVizzyHost(): VizzyHostHandle {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [state, setState] = useState<VizzyState>(EMPTY_STATE);
  const [busy, setBusy] = useState<"save" | "open" | "attach" | null>(null);
  const [closed, setClosed] = useState(false);

  useEffect(() => {
    const subscribe = window.camxora?.vizzy?.onState;
    if (!subscribe) return;
    return subscribe((next) => setState(next));
  }, []);

  useEffect(() => {
    if (closed) return;
    const element = containerRef.current;
    if (!element) return;

    let disposed = false;
    let raf = 0;

    const place = async (initial: boolean) => {
      const bounds = boundsOf(element);
      if (bounds.width < 2 || bounds.height < 2) return;
      if (initial) {
        setBusy((current) => current ?? "attach");
        const result = await window.camxora.vizzy.attach(bounds);
        if (!disposed && result.ok) setState(result.data);
        if (!disposed) setBusy((current) => (current === "attach" ? null : current));
        return;
      }
      await window.camxora.vizzy.setBounds(bounds);
    };

    void place(true);

    // A resize observer covers the sidebar, the window and route-driven layout;
    // the window listener covers moving the view when the window itself moves.
    const schedule = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => void place(false));
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(element);
    window.addEventListener("resize", schedule);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
      void window.camxora?.vizzy?.detach();
    };
  }, [closed]);

  const save = useCallback(async () => {
    if (busy) return;
    setBusy("save");
    try {
      const result = await window.camxora.vizzy.save();
      if (!result.ok) {
        setState((current) => ({ ...current, error: result.error.message }));
      } else {
        setState((current) => ({ ...current, dirty: false, path: result.data.path }));
      }
    } finally {
      setBusy(null);
    }
  }, [busy]);

  const open = useCallback(async () => {
    if (busy) return;
    setBusy("open");
    try {
      const result = await window.camxora.vizzy.open();
      if (!result.ok) {
        setState((current) => ({ ...current, error: result.error.message }));
      }
    } finally {
      setBusy(null);
    }
  }, [busy]);

  const reload = useCallback(async () => {
    await window.camxora.vizzy.reload();
    setState((current) => ({ ...current, error: null, crashed: false }));
  }, []);

  const closeEditor = useCallback(() => setClosed(true), []);
  const openEditor = useCallback(() => setClosed(false), []);

  return {
    state,
    busy,
    closed,
    containerRef,
    save,
    open,
    reload,
    closeEditor,
    openEditor,
  };
}
