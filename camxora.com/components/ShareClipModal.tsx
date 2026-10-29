"use client";

import { Icon } from "@/components/Icon";

type ShareTarget = {
  id: string;
  label: string;
  icon: string;
  background: string;
  href?: (url: string, title: string) => string;
};

const TARGETS: ShareTarget[] = [
  {
    id: "copy",
    label: "Copy Link",
    icon: "fa-link",
    background: "#2f7bf6",
  },
  {
    id: "whatsapp",
    label: "WhatsApp",
    icon: "fa-brands fa-whatsapp",
    background: "#25d366",
    href: (url, title) => `https://wa.me/?text=${encodeURIComponent(`${title} ${url}`)}`,
  },
  {
    id: "download",
    label: "Download",
    icon: "fa-download",
    background: "#a78bfa",
  },
  {
    id: "facebook",
    label: "Facebook",
    icon: "fa-brands fa-facebook-f",
    background: "#1877f2",
    href: (url) => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
  },
  {
    id: "telegram",
    label: "Telegram",
    icon: "fa-brands fa-telegram",
    background: "#2aabee",
    href: (url, title) =>
      `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`,
  },
  {
    id: "x",
    label: "X",
    icon: "fa-brands fa-x-twitter",
    background: "#000000",
    href: (url, title) =>
      `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`,
  },
  {
    id: "instagram",
    label: "Instagram",
    icon: "fa-brands fa-instagram",
    background: "#1f9c8b",
  },
  {
    id: "linkedin",
    label: "LinkedIn",
    icon: "fa-brands fa-linkedin-in",
    background: "#0a66c2",
    href: (url) => `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
  },
  {
    id: "more",
    label: "More",
    icon: "fa-ellipsis",
    background: "#111827",
  },
];

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
                  <i className={`icon ${target.icon}`} aria-hidden="true" />
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
