import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-border px-6 py-5">
      <div className="min-w-0">
        {eyebrow ? <p className="text-caption text-text-muted">{eyebrow}</p> : null}
        <h1 className="mt-1 text-page font-semibold text-text-primary">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-body text-text-secondary">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
