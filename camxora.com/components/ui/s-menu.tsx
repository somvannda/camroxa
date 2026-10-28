"use client";

import * as React from "react";

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/**
 * Thin wrappers that keep the existing `.s-menu*` visual language while using
 * Radix DropdownMenu for behaviour (portal, outside click, Escape, roving
 * focus, collision-aware positioning).
 *
 * Radix renders the content under <body>, so `--s-*` tokens are published on
 * `:root` as well as `.s-page` in globals.css.
 */
export type SMenuProps = {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
  sideOffset?: number;
  className?: string;
  style?: React.CSSProperties;
};

export function SMenu({
  trigger,
  children,
  align = "end",
  side = "bottom",
  sideOffset = 6,
  className,
  style,
}: SMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        side={side}
        sideOffset={sideOffset}
        className={cn("s-menu", className)}
        style={style}
      >
        {children}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export const SMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuItem>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuItem>
>(({ className, ...props }, ref) => (
  <DropdownMenuItem ref={ref} className={cn("s-menu-item", className)} {...props} />
));
SMenuItem.displayName = "SMenuItem";

export const SMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DropdownMenuSeparator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuSeparator>
>(({ className, ...props }, ref) => (
  <DropdownMenuSeparator ref={ref} className={cn("s-menu-sep", className)} {...props} />
));
SMenuSeparator.displayName = "SMenuSeparator";

export const SMenuCheckboxItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuCheckboxItem>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuCheckboxItem>
>(({ className, ...props }, ref) => (
  <DropdownMenuCheckboxItem
    ref={ref}
    className={cn("s-menu-item", className)}
    {...props}
  />
));
SMenuCheckboxItem.displayName = "SMenuCheckboxItem";

export const SMenuRadioGroup = DropdownMenuRadioGroup;

export const SMenuRadioItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuRadioItem>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuRadioItem>
>(({ className, ...props }, ref) => (
  <DropdownMenuRadioItem ref={ref} className={cn("s-menu-item", className)} {...props} />
));
SMenuRadioItem.displayName = "SMenuRadioItem";

export const SMenuSub = DropdownMenuSub;

export const SMenuSubTrigger = React.forwardRef<
  React.ElementRef<typeof DropdownMenuSubTrigger>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuSubTrigger>
>(({ className, children, ...props }, ref) => (
  <DropdownMenuSubTrigger
    ref={ref}
    className={cn("s-menu-item", className)}
    {...props}
  >
    {children}
  </DropdownMenuSubTrigger>
));
SMenuSubTrigger.displayName = "SMenuSubTrigger";

export const SMenuSubContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuSubContent>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuSubContent>
>(({ className, ...props }, ref) => (
  <DropdownMenuSubContent ref={ref} className={cn("s-menu", className)} {...props} />
));
SMenuSubContent.displayName = "SMenuSubContent";
