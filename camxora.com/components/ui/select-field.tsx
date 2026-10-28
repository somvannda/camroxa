"use client";

import * as React from "react";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * Radix Select requires every item to have a non-empty value, but several
 * Camxora pickers use "" for "none / all". Map it through a sentinel so the
 * public API can keep using plain empty strings.
 */
const EMPTY_VALUE = "__camxora_empty__";

export type SelectFieldOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export type SelectFieldProps = {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectFieldOption[];
  /** Accessible name when the trigger is not wrapped in a <label>. */
  ariaLabel?: string;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
  /** Trigger classes (existing page styles such as `.s-input` still apply). */
  className?: string;
  /** Menu classes. */
  contentClassName?: string;
  /** Optional group label rendered above the options. */
  groupLabel?: string;
  /** Use the dense 24-28px control used inside the studio editors. */
  size?: "default" | "sm";
};

export const SelectField = React.forwardRef<HTMLButtonElement, SelectFieldProps>(
  function SelectField(
    {
      value,
      onValueChange,
      options,
      ariaLabel,
      id,
      placeholder,
      disabled,
      className,
      contentClassName,
      groupLabel,
      size = "default",
    },
    ref
  ) {
    const encode = (raw: string) => (raw === "" ? EMPTY_VALUE : raw);
    const decode = (raw: string) => (raw === EMPTY_VALUE ? "" : raw);

    const items = options.map((option) => (
      <SelectItem
        key={option.value === "" ? EMPTY_VALUE : option.value}
        value={encode(option.value)}
        disabled={option.disabled}
      >
        {option.label}
      </SelectItem>
    ));

    return (
      <Select
        value={encode(value)}
        onValueChange={(next) => onValueChange(decode(next))}
        disabled={disabled}
      >
        <SelectTrigger
          ref={ref}
          id={id}
          aria-label={ariaLabel}
          className={cn(
            "select-field",
            size === "sm" && "select-field-sm",
            className
          )}
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent className={cn("select-field-content", contentClassName)}>
          {groupLabel ? (
            <SelectGroup>
              <SelectLabel>{groupLabel}</SelectLabel>
              {items}
            </SelectGroup>
          ) : (
            items
          )}
        </SelectContent>
      </Select>
    );
  }
);
