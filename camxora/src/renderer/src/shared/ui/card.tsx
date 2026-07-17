import * as React from 'react'

import { cn } from '@/shared/lib/utils'

export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>): React.JSX.Element {
  return (
    <div
      className={cn(
        'rounded-2xl border border-white/10 bg-slate-900/75 shadow-[0_20px_80px_-40px_rgba(124,58,237,0.55)] backdrop-blur',
        className,
      )}
      {...props}
    />
  )
}
