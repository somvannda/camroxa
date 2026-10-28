"use client";

import { useRef } from "react";

type CodeInputProps = {
  value: string;
  onChange: (value: string) => void;
  length?: number;
  ariaLabel?: string;
};

export function CodeInput({
  value,
  onChange,
  length = 6,
  ariaLabel = "Verification code",
}: CodeInputProps) {
  const inputs = useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length }, (_, index) => value[index] ?? "");

  const focusAt = (index: number) => {
    const next = Math.max(0, Math.min(length - 1, index));
    inputs.current[next]?.focus();
    inputs.current[next]?.select();
  };

  const setDigits = (next: string[]) => {
    onChange(next.join("").slice(0, length));
  };

  const handleChange = (index: number, raw: string) => {
    const clean = raw.replace(/\D/g, "");
    if (!clean) return;

    if (clean.length > 1) {
      const next = [...digits];
      clean
        .slice(0, length - index)
        .split("")
        .forEach((char, offset) => {
          next[index + offset] = char;
        });
      setDigits(next);
      focusAt(index + clean.length);
      return;
    }

    const next = [...digits];
    next[index] = clean.slice(-1);
    setDigits(next);
    focusAt(index + 1);
  };

  const handleKeyDown = (index: number, event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Backspace") {
      if (digits[index]) {
        const next = [...digits];
        next[index] = "";
        setDigits(next);
      } else if (index > 0) {
        const next = [...digits];
        next[index - 1] = "";
        setDigits(next);
        focusAt(index - 1);
      }
      event.preventDefault();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusAt(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      focusAt(index + 1);
    }
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!pasted) return;
    onChange(pasted);
    focusAt(pasted.length);
  };

  return (
    <div className="code-input" role="group" aria-label={ariaLabel}>
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(element) => {
            inputs.current[index] = element;
          }}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={1}
          value={digit}
          autoComplete={index === 0 ? "one-time-code" : "off"}
          aria-label={`${ariaLabel} digit ${index + 1}`}
          className={digit ? "filled" : ""}
          onChange={(event) => handleChange(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          onPaste={handlePaste}
          onFocus={(event) => event.currentTarget.select()}
        />
      ))}
    </div>
  );
}
