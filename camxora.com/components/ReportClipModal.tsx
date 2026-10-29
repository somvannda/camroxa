"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";
import type { WebMusicReportReason } from "@/lib/web-music-api";

const REASONS: Array<{ id: WebMusicReportReason; label: string }> = [
  { id: "copyright", label: "Copyright" },
  { id: "explicit", label: "Explicit content" },
  { id: "spam", label: "Spam" },
  { id: "harassment", label: "Harassment" },
  { id: "other", label: "Other" },
];

export function ReportClipModal({
  title,
  busy = false,
  onClose,
  onSubmit,
}: {
  title: string;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (input: {
    reason: WebMusicReportReason;
    details: string;
  }) => Promise<void> | void;
}) {
  const [reason, setReason] = useState<WebMusicReportReason>("copyright");
  const [details, setDetails] = useState("");

  return (
    <div
      className="s-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Report clip"
      onClick={onClose}
    >
      <div
        className="s-modal"
        style={{ width: "min(440px,100%)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="s-modal-head">
          <h3>Report “{title}”</h3>
          <button
            type="button"
            className="s-btn s-btn-icon sm"
            aria-label="Close"
            onClick={onClose}
          >
            <Icon name="fa-xmark" />
          </button>
        </div>
        <div className="s-modal-body">
          <p className="s-note">Tell us what is wrong. Reports are private.</p>
          <div className="s-chip-row" role="group" aria-label="Report reason">
            {REASONS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`s-chip${reason === option.id ? " on" : ""}`}
                aria-pressed={reason === option.id}
                onClick={() => setReason(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <textarea
            className="s-input"
            rows={3}
            maxLength={1000}
            placeholder="Anything else we should know? (optional)"
            value={details}
            onChange={(event) => setDetails(event.target.value)}
            aria-label="Report details"
          />
        </div>
        <div className="s-modal-foot">
          <span style={{ flex: 1 }} />
          <button type="button" className="s-btn s-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="s-btn s-btn-danger"
            disabled={busy}
            onClick={() => void onSubmit({ reason, details })}
          >
            {busy ? "Sending…" : "Report"}
          </button>
        </div>
      </div>
    </div>
  );
}
