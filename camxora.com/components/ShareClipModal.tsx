"use client";

import { Icon } from "@/components/Icon";

type ShareGlyph =
  | "link"
  | "whatsapp"
  | "facebook"
  | "telegram"
  | "x"
  | "instagram"
  | "linkedin"
  | "download"
  | "more";

type ShareTarget = {
  id: string;
  label: string;
  glyph: ShareGlyph;
  background: string;
  href?: (url: string, title: string) => string;
};

const TARGETS: ShareTarget[] = [
  {
    id: "copy",
    label: "Copy Link",
    glyph: "link",
    background: "#2f7bf6",
  },
  {
    id: "whatsapp",
    label: "WhatsApp",
    glyph: "whatsapp",
    background: "#25d366",
    href: (url, title) =>
      `https://wa.me/?text=${encodeURIComponent(`${title} ${url}`)}`,
  },
  {
    id: "download",
    label: "Download",
    glyph: "download",
    background: "#a78bfa",
  },
  {
    id: "facebook",
    label: "Facebook",
    glyph: "facebook",
    background: "#1877f2",
    href: (url) =>
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
  },
  {
    id: "telegram",
    label: "Telegram",
    glyph: "telegram",
    background: "#2aabee",
    href: (url, title) =>
      `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`,
  },
  {
    id: "x",
    label: "X",
    glyph: "x",
    background: "#000000",
    href: (url, title) =>
      `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`,
  },
  {
    id: "instagram",
    label: "Instagram",
    glyph: "instagram",
    background: "#1f9c8b",
  },
  {
    id: "linkedin",
    label: "LinkedIn",
    glyph: "linkedin",
    background: "#0a66c2",
    href: (url) =>
      `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
  },
  {
    id: "more",
    label: "More",
    glyph: "more",
    background: "#111827",
  },
];

/**
 * Inline SVG so the share sheet never depends on an icon font being loaded or
 * containing the right brand glyph.
 */
function ShareIcon({ glyph }: { glyph: ShareGlyph }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (glyph) {
    case "link":
      return (
        <svg {...common}>
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      );
    case "whatsapp":
      return (
        <svg {...common}>
          <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
          <path d="M8.5 8.5c0 3.9 3.1 7 7 7l1.2-2-2.2-1-1 1a5.6 5.6 0 0 1-3-3l1-1-1-2.2Z" />
        </svg>
      );
    case "facebook":
      return (
        <svg {...common}>
          <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3Z" />
        </svg>
      );
    case "telegram":
      return (
        <svg {...common}>
          <path d="m22 2-7 20-4-9-9-4Z" />
          <path d="M22 2 11 13" />
        </svg>
      );
    case "x":
      return (
        <svg {...common}>
          <path d="M18 6 6 18" />
          <path d="m6 6 12 12" />
        </svg>
      );
    case "instagram":
      return (
        <svg {...common}>
          <rect x="2" y="2" width="20" height="20" rx="5" />
          <circle cx="12" cy="12" r="4" />
          <path d="M17.5 6.5h.01" />
        </svg>
      );
    case "linkedin":
      return (
        <svg {...common}>
          <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6Z" />
          <rect x="2" y="9" width="4" height="12" />
          <path d="M4 4h.01" />
        </svg>
      );
    case "download":
      return (
        <svg {...common}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <path d="m7 10 5 5 5-5" />
          <path d="M12 15V3" />
        </svg>
      );
    case "more":
      return (
        <svg {...common}>
          <path d="M5 12h.01" />
          <path d="M12 12h.01" />
          <path d="M19 12h.01" />
        </svg>
      );
  }
}

export function ShareClipModal({
  url,
  title,
  downloadUrl,
  onClose,
  onToast,
}: {
  url: string;
  title: string;
  downloadUrl?: string;
  onClose: () => void;
  onToast?: (message: string) => void;
}) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      onToast?.("Link copied");
    } catch {
      onToast?.(url);
    }
  }

  async function nativeShare() {
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        /* user cancelled */
      }
    }
    await copy();
  }

  async function handle(target: ShareTarget) {
    if (target.id === "copy") {
      await copy();
      return;
    }
    if (target.id === "download") {
      if (downloadUrl) {
        window.open(downloadUrl, "_blank", "noopener");
      } else {
        onToast?.("Download is not ready yet");
      }
      return;
    }
    if (target.id === "more") {
      await nativeShare();
      return;
    }
    if (target.id === "instagram") {
      // Instagram has no web share endpoint: copy the link so it can be pasted.
      await copy();
      onToast?.("Link copied — paste it into Instagram");
      return;
    }
    if (target.href) {
      window.open(target.href(url, title), "_blank", "noopener,noreferrer");
      return;
    }
    await nativeShare();
  }

  return (
    <div
      className="s-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Share"
      onClick={onClose}
    >
      <div
        className="s-modal s-share-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="s-modal-head">
          <h3>Share to…</h3>
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
          <div className="s-share-grid">
            {TARGETS.map((target) => (
              <button
                key={target.id}
                type="button"
                className="s-share-target"
                onClick={() => void handle(target)}
              >
                <span
                  className="s-share-icon"
                  style={{ background: target.background }}
                >
                  <ShareIcon glyph={target.glyph} />
                </span>
                <span className="s-share-label">{target.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
