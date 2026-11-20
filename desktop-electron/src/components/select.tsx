import * as SelectPrimitive from "@radix-ui/react-select";
import { Icon } from "./icon";
import { classNames } from "../lib/format";
import type { ControlSize } from "./control-size";
import type { ReactNode } from "react";

const SIZES: Record<ControlSize, string> = {
  sm: "h-7 text-caption",
  md: "h-8 text-body",
  lg: "h-9 text-body",
};

export interface SelectOption {
  value: string | number;
  label: ReactNode;
  disabled?: boolean;
}

export interface SelectProps {
  id?: string;
  value?: string | number;
  onValueChange?: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  name?: string;
  controlSize?: ControlSize;
  invalid?: boolean;
  className?: string;
  wrapperClassName?: string;
  "data-testid"?: string;
  "aria-label"?: string;
}

/** Radix-backed dropdown: one custom listbox for every page. */
export function Select({
  id,
  value,
  onValueChange,
  options,
  placeholder = "Select",
  disabled,
  required,
  name,
  controlSize = "md",
  invalid = false,
  className,
  wrapperClassName,
  "data-testid": testId,
  "aria-label": ariaLabel,
}: SelectProps) {
  const raw = value === undefined || value === null ? "" : String(value);
  // Radix reserves "" for the placeholder, so an explicit empty option uses a
  // sentinel and is mapped back before it reaches the caller.
  const EMPTY = "__empty__";
  const current = raw === "" ? undefined : raw;
  const emptyOption = options.find((option) => String(option.value) === "");

  const mapped = options.map((option) => ({
    ...option,
    value: String(option.value) === "" ? EMPTY : String(option.value),
  }));
  if (emptyOption && !mapped.some((option) => option.value === EMPTY)) {
    mapped.unshift({ ...emptyOption, value: EMPTY });
  }

  return (
    <div className={classNames("relative w-full", wrapperClassName)}>
      <SelectPrimitive.Root
      value={current ?? (emptyOption ? EMPTY : undefined)}
      onValueChange={(next) => onValueChange?.(next === EMPTY ? "" : next)}
      disabled={disabled}
      required={required}
      name={name}
    >
      <SelectPrimitive.Trigger
        id={id}
        data-testid={testId}
        data-selected-value={raw}
        aria-label={ariaLabel}
        className={classNames(
          "flex w-full items-center justify-between gap-2 rounded-control border bg-surface-1 px-2 text-left text-text-primary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-40",
          SIZES[controlSize],
          invalid ? "border-danger focus:border-danger" : "border-border",
          className,
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon asChild>
          <Icon name="fa-chevron-down" size={9} className="shrink-0 text-text-muted" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          collisionPadding={8}
          className="z-[90] max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-card border border-border bg-surface-1 shadow-[0_18px_48px_rgba(0,0,0,.5)]"
        >
          <SelectPrimitive.Viewport className="p-1">
            {mapped.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                data-value={String(option.value) === EMPTY ? "" : option.value}
                className="relative flex h-7 cursor-pointer select-none items-center rounded-[5px] pl-7 pr-2 text-body text-text-secondary outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40 data-[highlighted]:bg-surface-hover data-[highlighted]:text-text-primary data-[state=checked]:text-text-primary"
              >
                <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                  <SelectPrimitive.ItemIndicator>
                    <Icon name="fa-check" size={10} className="text-accent" />
                  </SelectPrimitive.ItemIndicator>
                </span>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
    </div>
  );
}
