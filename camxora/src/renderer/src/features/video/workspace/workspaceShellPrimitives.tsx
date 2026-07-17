import { cn } from '@/shared/lib/utils'

export function SummaryField(props: { label: string; value: string }): React.JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-[#081028] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{props.label}</p>
      <p className="mt-0.5 text-xs font-medium text-slate-100">{props.value}</p>
    </div>
  )
}

export function WorkspaceBadge(props: {
  label: string
  tone?: 'neutral' | 'ready' | 'warning' | 'running'
}): React.JSX.Element {
  const toneClassName =
    props.tone === 'ready'
      ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200'
      : props.tone === 'warning'
        ? 'border-amber-400/30 bg-amber-500/10 text-amber-200'
        : props.tone === 'running'
          ? 'border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-200'
          : 'border-white/10 bg-white/5 text-slate-300'

  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-1 text-[10px] font-medium tracking-[0.14em]', toneClassName)}>
      {props.label}
    </span>
  )
}

export function WorkspaceAssetCard(props: {
  label: string
  value: string
  detail: string
  tone?: 'neutral' | 'ready' | 'warning'
}): React.JSX.Element {
  const toneClassName =
    props.tone === 'ready'
      ? 'border-emerald-400/20'
      : props.tone === 'warning'
        ? 'border-amber-400/20'
        : 'border-white/10'

  return (
    <div className={cn('rounded-2xl border bg-[#081028] px-3 py-2.5', toneClassName)}>
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{props.label}</p>
      <p className="mt-1 truncate text-xs font-medium text-slate-100">{props.value}</p>
      <p className="mt-1 truncate text-[10px] text-slate-500">{props.detail}</p>
    </div>
  )
}
