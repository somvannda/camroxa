"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { helpFor, SHORTCUTS, type HelpEntry } from "@/lib/studio-help";

/**
 * Learn menu + What's This? hover help (reference §7 / §38).
 *
 * A popover, not a dialog: it does not dim the editor or trap focus, and it closes on an
 * outside click. Keyboard Shortcuts and the Learning Center open in-app dialogs. The
 * reference's YouTube Tutorials row is intentionally dropped: this product has no
 * tutorial channel, and a permanently disabled row is not a feature.
 *
 * What's This? is the real feature: any control carrying `data-help` gets a light card
 * with a name and a sentence, toggled globally and persisted in Studio settings.
 */

const SEEN_KEY = "studio:help:seen";

/** Short, product-true tour; every step maps to a control that exists in this editor. */
const LEARNING_STEPS = [
  {
    title: "Start an arrangement",
    body: "Press A for an audio track or M for a MIDI track, or drag a song in from the Library.",
  },
  {
    title: "Create a part",
    body: "Use the prompt bar at the bottom; generated takes land on the selected track as clips.",
  },
  {
    title: "Shape the sound",
    body: "Add an effect from the dock, then drag its knobs. Bypass, reorder or pop out any slot.",
  },
  {
    title: "Edit the timeline",
    body: "Drag on the ruler to select a range; split, duplicate, loop or export it from the range menu.",
  },
  {
    title: "Save and mirror",
    body: "Edits autosave. The sync chip sends the arrangement to Suno and reports conflicts honestly.",
  },
];

export type StudioLearnProps = {
  whatsThis: boolean;
  onWhatsThis: (next: boolean) => void;
};

function markSeen() {
  try {
    window.localStorage.setItem(SEEN_KEY, "1");
  } catch {
    /* storage may be unavailable; the card still dismisses for this session */
  }
}

function hasSeen() {
  try {
    return window.localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

export function StudioLearn({ whatsThis, onWhatsThis }: StudioLearnProps) {
  const [open, setOpen] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);
  const [learning, setLearning] = useState(false);
  const [card, setCard] = useState<{ entry: HelpEntry; left: number; top: number } | null>(null);
  const [firstRun, setFirstRun] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setFirstRun(whatsThis && !hasSeen());
  }, [whatsThis]);

  // Outside click closes the popover; Escape closes every layer we opened.
  useEffect(() => {
    if (!open && !card && !shortcuts && !learning) return;
    const onPointer = (event: PointerEvent) => {
      const root = rootRef.current;
      if (open && root && !root.contains(event.target as Node)) setOpen(false);
      if (card && !(event.target as HTMLElement)?.closest?.("[data-help]")) setCard(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        setShortcuts(false);
        setLearning(false);
        setCard(null);
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, card, shortcuts, learning]);

  // `?` opens the shortcut list — the accelerator the Learn menu advertises.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "?" || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
      ) {
        return;
      }
      // A dialog owns the keyboard while it is open; do not open help behind it.
      if (document.querySelector('[role="dialog"][aria-modal="true"], [role="alertdialog"]')) return;
      event.preventDefault();
      setOpen(false);
      setCard(null);
      setShortcuts(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Hover / focus help. One delegated listener, so controls only opt in with data-help.
  useEffect(() => {
    if (!whatsThis) {
      setCard(null);
      return;
    }
    const showFor = (element: HTMLElement | null) => {
      const entry = helpFor(element?.dataset.help);
      if (!entry || !element) {
        setCard(null);
        return;
      }
      const rect = element.getBoundingClientRect();
      const width = 256;
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      const below = rect.bottom + 8;
      const top = below + 140 > window.innerHeight ? Math.max(8, rect.top - 148) : below;
      setCard({ entry, left, top });
    };
    const onOver = (event: Event) => {
      const target = event.target as HTMLElement | null;
      showFor(target?.closest?.("[data-help]") as HTMLElement | null);
    };
    const onOut = (event: Event) => {
      const target = event.target as HTMLElement | null;
      const owner = target?.closest?.("[data-help]") as HTMLElement | null;
      if (!owner) return;
      const next = (event as PointerEvent).relatedTarget as HTMLElement | null;
      if (next && owner.contains(next)) return;
      setCard(null);
    };
    const hide = () => setCard(null);
    document.addEventListener("pointerover", onOver);
    document.addEventListener("pointerout", onOut);
    document.addEventListener("focusin", onOver);
    window.addEventListener("scroll", hide, true);
    return () => {
      document.removeEventListener("pointerover", onOver);
      document.removeEventListener("pointerout", onOut);
      document.removeEventListener("focusin", onOver);
      window.removeEventListener("scroll", hide, true);
    };
  }, [whatsThis]);

  function dismissFirstRun() {
    markSeen();
    setFirstRun(false);
  }

  function turnOff() {
    markSeen();
    setFirstRun(false);
    setCard(null);
    onWhatsThis(false);
  }

  return (
    <div className="se-learn" ref={rootRef}>
      {card ? (
        <div
          className="se-help-card"
          role="tooltip"
          style={{ left: card.left, top: card.top }}
        >
          <strong>{card.entry.title}</strong>
          <span>{card.entry.body}</span>
        </div>
      ) : null}

      {firstRun ? (
        <div className="se-help-card se-help-first" role="note">
          <strong>What&apos;s This?</strong>
          <span>
            Hover over any control to see what it does. You can turn this off from Learn.
          </span>
          <div className="se-help-actions">
            <button type="button" className="se-pill" onClick={dismissFirstRun}>
              Dismiss
            </button>
            <button type="button" className="se-pill on" onClick={turnOff}>
              Turn off
            </button>
          </div>
        </div>
      ) : null}

      <button
        type="button"
        className={`se-learn-pill${open ? " on" : ""}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="fa-lightbulb" /> Learn
      </button>

      {open ? (
        <div className="se-learn-menu" role="menu" aria-label="Learn">
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              setShortcuts(true);
            }}
          >
            <Icon name="fa-list" /> Keyboard Shortcuts <span>shift ?</span>
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              setLearning(true);
            }}
          >
            <Icon name="fa-circle-info" /> Learning Center
          </button>
          <button
            type="button"
            role="menuitemcheckbox"
            aria-checked={whatsThis}
            onClick={() => {
              markSeen();
              setFirstRun(false);
              onWhatsThis(!whatsThis);
            }}
          >
            <Icon name="fa-lightbulb" /> What&apos;s This?{" "}
            <span>{whatsThis ? "On" : "Off"}</span>
          </button>
        </div>
      ) : null}

      {learning ? (
        <div
          className="se-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Learning Center"
        >
          <div className="se-dialog">
            <h2>Learning Center</h2>
            <p className="se-dialog-note">
              Five things to try first. Press ? at any time for the full shortcut map.
            </p>
            <ol className="se-dialog-list">
              {LEARNING_STEPS.map((step) => (
                <li key={step.title} className="se-dialog-row">
                  <span className="se-dialog-title">{step.title}</span>
                  <span className="se-dialog-note">{step.body}</span>
                </li>
              ))}
            </ol>
            <div className="se-dialog-foot">
              <button type="button" className="se-pill" onClick={() => setLearning(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {shortcuts ? (
        <div
          className="se-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Keyboard shortcuts"
        >
          <div className="se-dialog">
            <h2>Keyboard shortcuts</h2>
            <ul className="se-dialog-list">
              {SHORTCUTS.map((row) => (
                <li key={row.keys} className="se-dialog-row">
                  <span className="se-dialog-title">{row.action}</span>
                  <kbd>{row.keys}</kbd>
                </li>
              ))}
            </ul>
            <div className="se-dialog-foot">
              <button type="button" className="se-pill" onClick={() => setShortcuts(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
