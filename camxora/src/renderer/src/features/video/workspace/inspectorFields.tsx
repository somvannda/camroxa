import { useId } from 'react'

import { cn } from '@/shared/lib/utils'
import { AppSelect } from '@/shared/ui/app-select'
import { InlineToggle } from '@/shared/ui/inline-toggle'
import { Input } from '@/shared/ui/input'

export function SectionCard(props: {
  title: string
  subtitle: string
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <div className="min-w-0 w-full rounded-2xl border border-white/10 bg-[#081028] p-2.5">
      <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-200">{props.title}</h3>
      {props.subtitle ? <p className="mt-1 text-[10px] leading-4 text-slate-500">{props.subtitle}</p> : null}
      <div className="mt-2.5 grid gap-2.5">{props.children}</div>
    </div>
  )
}

export function SelectField(props: {
  label: string
  description?: string
  disabled?: boolean
  placeholder?: string
  value: string
  options: ReadonlyArray<{ value: string; label: string }>
  onChange: (nextValue: string) => void
}): React.JSX.Element {
  return (
    <div className="grid gap-1.5">
      <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">
        {props.label}
        {props.description ? (
          <span className="mt-1 block text-[10px] font-normal leading-4 text-slate-500">{props.description}</span>
        ) : null}
      </div>
      <AppSelect
        disabled={props.disabled}
        options={props.options}
        placeholder={props.placeholder ?? props.label}
        triggerClassName="h-9 bg-slate-950/70 text-xs"
        value={props.value}
        onChange={props.onChange}
      />
    </div>
  )
}

export function SliderField(props: {
  label: string
  description?: string
  value: number
  min: number
  max: number
  step?: number
  format?: (value: number) => string
  onChange: (nextValue: number) => void
  onChangeCommitted?: (nextValue: number) => void
}): React.JSX.Element {
  const handleCommittedChange = (value: string) => {
    props.onChangeCommitted?.(Number(value))
  }
  const hasInlineValue = props.label.includes('(')
  const accessibleLabel = props.label.replace(/\s*\([^)]*\)\s*$/, '').trim() || props.label

  return (
    <div className="grid gap-1">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">{props.label}</p>
        {props.description ? <p className="text-[10px] leading-4 text-slate-500">{props.description}</p> : null}
      </div>
      <input
        aria-label={accessibleLabel}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-fuchsia-500"
        max={props.max}
        min={props.min}
        step={props.step ?? 1}
        type="range"
        value={props.value}
        onChange={(event) => props.onChange(Number(event.target.value))}
        onBlur={(event) => handleCommittedChange(event.target.value)}
        onKeyUp={(event) => handleCommittedChange((event.currentTarget as HTMLInputElement).value)}
        onPointerUp={(event) => handleCommittedChange((event.currentTarget as HTMLInputElement).value)}
      />
      {hasInlineValue ? null : (
        <div className="text-right text-[10px] font-medium tabular-nums text-slate-500">
          {props.format ? props.format(props.value) : props.value.toFixed(props.step && props.step < 1 ? 2 : 0)}
        </div>
      )}
    </div>
  )
}

export function ToggleField(props: {
  label: string
  description?: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}): React.JSX.Element {
  return (
    <label
      className={cn(
        'flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-2.5 py-2',
        props.disabled && 'opacity-60',
      )}
    >
      <div>
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">{props.label}</p>
        {props.description ? <p className="mt-1 text-[10px] leading-4 text-slate-500">{props.description}</p> : null}
      </div>
      <InlineToggle
        disabled={props.disabled}
        showLabel={false}
        className="h-7 rounded-lg px-2 text-[10px]"
        label={props.label}
        pressed={props.checked}
        onPressedChange={props.onChange}
      />
    </label>
  )
}

export function ColorField(props: {
  label: string
  value: string
  onChange: (nextValue: string) => void
}): React.JSX.Element {
  const fieldId = useId()
  const normalized = String(props.value || '').trim()
  const pickerValue = normalized && normalized.startsWith('#') ? normalized : '#000000'

  return (
    <div className="grid gap-1.5">
      <label className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500" htmlFor={fieldId}>
        {props.label}
      </label>
      <div className="flex min-w-0 items-center gap-3">
        <div className="relative h-6 w-6 shrink-0">
          <div className="h-6 w-6 rounded-full border border-white/10" style={{ backgroundColor: props.value }} />
          <input
            aria-label={`${props.label} color`}
            className="absolute inset-0 h-6 w-6 cursor-pointer opacity-0"
            type="color"
            value={pickerValue}
            onChange={(event) => props.onChange(event.target.value)}
          />
        </div>
        <Input
          className="h-9 min-w-0 flex-1 bg-slate-950/70 text-xs"
          id={fieldId}
          value={props.value}
          onChange={(event) => props.onChange(event.target.value)}
        />
      </div>
    </div>
  )
}
