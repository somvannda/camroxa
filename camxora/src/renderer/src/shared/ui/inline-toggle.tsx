import { cn } from '@/shared/lib/utils'

export function InlineToggle(props: {
  label: string
  pressed: boolean
  onPressedChange: (pressed: boolean) => void
  disabled?: boolean
  showLabel?: boolean
  className?: string
}): React.JSX.Element {
  const showLabel = props.showLabel ?? true
  const text = showLabel ? props.label : props.pressed ? 'ON' : 'OFF'
  return (
    <button
      aria-disabled={props.disabled}
      aria-label={props.label}
      aria-pressed={props.pressed}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-xl border px-2.5 text-[11px] font-medium transition',
        props.pressed
          ? 'border-fuchsia-400/35 bg-fuchsia-500/12 text-fuchsia-100'
          : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:text-white',
        props.disabled && 'cursor-not-allowed opacity-60 hover:border-white/10 hover:text-slate-300',
        props.className,
      )}
      disabled={props.disabled}
      type="button"
      onClick={() => props.onPressedChange(!props.pressed)}
    >
      <span
        className={cn(
          'h-2.5 w-2.5 rounded-full border',
          props.pressed ? 'border-fuchsia-300 bg-fuchsia-300' : 'border-slate-500 bg-transparent',
        )}
      />
      {text}
    </button>
  )
}
