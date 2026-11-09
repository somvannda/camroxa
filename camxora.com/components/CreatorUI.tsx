import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
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
