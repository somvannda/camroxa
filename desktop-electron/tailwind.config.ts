import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: {
          1: "var(--surface-1)",
          2: "var(--surface-2)",
          3: "var(--surface-3)",
          hover: "var(--surface-hover)",
          active: "var(--surface-active)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
          disabled: "var(--text-disabled)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          ink: "var(--accent-ink)",
          soft: "var(--accent-soft)",
          line: "var(--accent-line)",
        },
        success: {
          DEFAULT: "var(--success)",
          soft: "var(--success-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          soft: "var(--warning-soft)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          soft: "var(--danger-soft)",
        },
        info: {
          DEFAULT: "var(--info)",
          soft: "var(--info-soft)",
        },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        control: "8px",
        card: "12px",
        overlay: "14px",
      },
      fontSize: {
        caption: ["11px", { lineHeight: "15px" }],
        meta: ["12px", { lineHeight: "16px" }],
        body: ["13px", { lineHeight: "19px" }],
        title: ["16px", { lineHeight: "22px" }],
        page: ["24px", { lineHeight: "30px" }],
      },
      spacing: {
        4.5: "18px",
      },
    },
  },
  plugins: [],
} satisfies Config;
