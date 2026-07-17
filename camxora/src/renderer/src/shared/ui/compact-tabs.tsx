import { cn } from '@/shared/lib/utils'

export type CompactTabOption = {
  value: string
  label: string
  icon?: React.ComponentType<{ className?: string }>
}

export function CompactTabs(props: {
  value: string
  options: ReadonlyArray<CompactTabOption>
  onChange: (value: string) => void
  className?: string
  listClassName?: string
  justify?: boolean
}): React.JSX.Element {
  return (
    <div className={cn('rounded-2xl border border-white/10 bg-[#081028] p-0.5', props.className)}>
      <div className={cn(props.justify ? 'grid grid-cols-[repeat(auto-fit,minmax(0,1fr))] gap-1' : 'flex flex-nowrap gap-1 overflow-x-auto', props.listClassName)}>
        {props.options.map((option) => {
          const active = option.value === props.value
          const Icon = option.icon
          return (
            <button
              aria-selected={active}
              className={cn(
                'inline-flex h-7 items-center gap-2 rounded-xl px-2.5 text-[11px] font-medium transition',
                props.justify ? 'min-w-0 justify-center' : 'shrink-0',
                active
                  ? 'bg-fuchsia-500/15 text-white'
                  : 'text-slate-300 hover:bg-white/5 hover:text-white',
              )}
              key={option.value}
              type="button"
              onClick={() => props.onChange(option.value)}
            >
              {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
