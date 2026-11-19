import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        sidebar: "var(--sidebar)",
        field: "var(--field)",
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
        sans: ["Inter Variable", "Inter", "Niradei", "Noto Sans Khmer", "Segoe UI", "system-ui", "sans-serif"],
        display: ["Niradei", "Inter Variable", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      borderRadius: {
        control: "10px",
        card: "12px",
        overlay: "16px",
      },
      fontSize: {
        caption: ["11px", { lineHeight: "15px" }],
        meta: ["12px", { lineHeight: "17px" }],
        body: ["14px", { lineHeight: "20px" }],
        "body-sm": ["13px", { lineHeight: "19px" }],
        title: ["16px", { lineHeight: "22px" }],
        subhead: ["18px", { lineHeight: "24px" }],
        page: ["28px", { lineHeight: "34px" }],
        hero: ["30px", { lineHeight: "36px" }],
      },
      spacing: {
        4.5: "18px",
      },
    },
  },
  plugins: [],
} satisfies Config;
