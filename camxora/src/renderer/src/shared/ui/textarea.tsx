import * as React from 'react'

import { cn } from '@/shared/lib/utils'

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-[120px] w-full resize-none rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-fuchsia-500/80 focus:ring-2 focus:ring-fuchsia-500/20',
        className,
      )}
      {...props}
    />
  ),
)

Textarea.displayName = 'Textarea'

