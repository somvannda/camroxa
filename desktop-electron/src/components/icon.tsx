import { classNames } from "../lib/format";

/**
 * Font Awesome 6 icon, matching camxora.com's `Icon` component.
 * The glyph is centred inside a fixed box so icons and labels share one optical
 * centre. Name examples: "fa-house", "fa-music", "fa-gear".
 */
export function Icon({
  name,
  size = 16,
  className,
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  return (
    <i
      aria-hidden="true"
      className={classNames("icon fa-classic fa-solid fa-replaced", name, className)}
      style={{ width: size, height: size, fontSize: size }}
    />
  );
}
