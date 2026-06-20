import * as React from "react";
import { cn } from "@/lib/utils";

type Props = {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onValueChange: (next: number) => void;
  className?: string;
  onDragStart?: () => void;
  onDragEnd?: () => void;
};

export function Slider({ value, min = 0, max = 100, step = 1, onValueChange, className, onDragStart, onDragEnd }: Props) {
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onValueChange(Number(e.target.value))}
      onPointerDown={() => onDragStart?.()}
      onPointerUp={() => onDragEnd?.()}
      onPointerCancel={() => onDragEnd?.()}
      className={cn(
        "h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-800/70",
        "[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500",
        "[&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-blue-500",
        className,
      )}
    />
  );
}

