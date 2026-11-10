"use client";

import * as Checkbox from "@radix-ui/react-checkbox";
import * as Select from "@radix-ui/react-select";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import styles from "./creator-ui.module.css";

type ButtonVariant = "primary" | "secondary" | "ghost";

export function CreatorPage({ children }: { children: ReactNode }) {
  return <div className={styles.page}>{children}</div>;
}

export function CreatorHeader({
  meta,
  title,
  description,
  actions,
}: {
  meta?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div>
        {meta ? <p className={styles.meta}>{meta}</p> : null}
        <h1 className={styles.title}>{title}</h1>
        {description ? <p className={styles.subtitle}>{description}</p> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}

export function CreatorPanel({
  title,
  meta,
  children,
  className = "",
}: {
  title?: string;
  meta?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`${styles.panel} ${className}`.trim()}>
      {title ? (
        <div className={styles.panelHeader}>
          <h2 className={styles.panelTitle}>{title}</h2>
          {meta ? <span className={styles.panelMeta}>{meta}</span> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function CreatorField({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={htmlFor}>{label}</label>
      {children}
      {hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  );
}

export function creatorButtonClass(variant: ButtonVariant = "primary"): string {
  return styles[variant];
}

export function CreatorButton({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={`${creatorButtonClass(variant)} ${className}`.trim()}
      {...props}
    />
  );
}

export function CreatorButtonLink({
  href,
  variant = "secondary",
  children,
}: {
  href: string;
  variant?: ButtonVariant;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={creatorButtonClass(variant)}>
      {children}
    </Link>
  );
}

export function CreatorInput({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${styles.input} ${className}`.trim()} {...props} />;
}

export function CreatorTextarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${styles.textarea} ${className}`.trim()} {...props} />;
}

export function CreatorSelect({
  id,
  value,
  onValueChange,
  options,
  placeholder = "Select",
  ariaLabel,
}: {
  id?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  ariaLabel?: string;
}) {
  return (
    <Select.Root value={value || undefined} onValueChange={onValueChange}>
      <Select.Trigger
        id={id}
        className={styles.selectTrigger}
        aria-label={ariaLabel}
      >
        <Select.Value placeholder={placeholder} />
        <Select.Icon className={styles.selectChevron}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path
              d="M3 4.5 6 7.5 9 4.5"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          className={styles.selectContent}
          position="popper"
          sideOffset={6}
        >
          <Select.Viewport className={styles.selectViewport}>
            {options.map((option) => (
              <Select.Item
                key={option.value}
                value={option.value}
                className={styles.selectItem}
              >
                <Select.ItemText>{option.label}</Select.ItemText>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}

export function CreatorCheckbox({
  id,
  checked,
  onCheckedChange,
  label,
  disabled = false,
}: {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className={styles.checkRow} htmlFor={id}>
      <Checkbox.Root
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={(value) => onCheckedChange(value === true)}
        className={styles.checkboxRoot}
      >
        <Checkbox.Indicator className={styles.checkboxIndicator}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path
              d="M2.5 6.2 4.8 8.5 9.5 3.5"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </Checkbox.Indicator>
      </Checkbox.Root>
      <span>{label}</span>
    </label>
  );
}

export function CreatorStatus({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "review" | "live" | "danger";
}) {
  const dot =
    tone === "live"
      ? styles.dotLive
      : tone === "review"
        ? styles.dotReview
        : tone === "danger"
          ? styles.dotDanger
          : "";
  return (
    <span className={styles.status}>
      <span className={`${styles.dot} ${dot}`.trim()} aria-hidden="true" />
      {label}
    </span>
  );
}

type ToastTone = "success" | "error" | "info";

export function useCreatorToast() {
  const [toast, setToast] = useState<{ message: string; tone: ToastTone } | null>(null);
  const showToast = useCallback((message: string, tone: ToastTone = "success") => {
    setToast({ message, tone });
  }, []);
  const dismiss = useCallback(() => setToast(null), []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return { toast, showToast, dismiss };
}

export function CreatorToast({
  toast,
  onDismiss,
}: {
  toast: { message: string; tone: ToastTone } | null;
  onDismiss: () => void;
}) {
  if (!toast) return null;
  const toneClass =
    toast.tone === "error"
      ? styles.toastError
      : toast.tone === "success"
        ? styles.toastSuccess
        : "";
  return (
    <div
      className={`${styles.toast} ${toneClass}`.trim()}
      role={toast.tone === "error" ? "alert" : "status"}
      aria-live={toast.tone === "error" ? "assertive" : "polite"}
    >
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss notification">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path
            d="M3 3l6 6M9 3l-6 6"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
