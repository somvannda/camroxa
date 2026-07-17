import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:pointer-events-none disabled:opacity-50 disabled:saturate-50 active:translate-y-px [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400 hover:shadow-[0_22px_54px_rgba(118,77,255,0.38)]",
        destructive:
          "border border-red-400/20 bg-red-500/90 text-white shadow-[0_10px_28px_rgba(239,68,68,0.24)] hover:bg-red-500",
        outline:
          "border border-white/10 bg-slate-950/70 text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] hover:border-slate-600 hover:bg-slate-900/80",
        secondary:
          "border border-white/10 bg-slate-900/90 text-slate-100 hover:bg-slate-800/90",
        ghost:
          "text-slate-300 hover:bg-slate-800/70 hover:text-white",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2.5",
        sm: "h-9 px-3.5 text-xs",
        lg: "h-11 px-8 text-sm",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
