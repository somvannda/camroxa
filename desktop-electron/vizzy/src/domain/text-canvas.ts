/**
 * Canvas2D text layout, decompiled from Vizzy module 461.
 *
 * It wraps lines to a fixed width, optionally justifies them with hair spaces,
 * aligns horizontally/vertically, and returns the total height. Keeping this
 * exact keeps text boxes and multi-line wrapping identical to the reference.
 */

export interface TextDrawOptions {
  x: number;
  y: number;
  width: number;
  height: number;
  debug?: boolean;
  align?: "left" | "center" | "right";
  vAlign?: "top" | "middle" | "bottom";
  fontSize: number;
  fontWeight?: string;
  fontStyle?: string;
  fontVariant?: string;
  font?: string;
  lineHeight?: number | null;
  justify?: boolean;
}

function justifyLine(options: {
  ctx: CanvasRenderingContext2D;
  line: string;
  spaceWidth: number;
  spaceChar: string;
  width: number;
}): string {
  const { ctx, line, spaceWidth, spaceChar, width } = options;
  const trimmed = line.trim();
  const words = trimmed.split(/\s+/);
  const gaps = words.length - 1;
  if (gaps === 0) return trimmed;
  const spare = (width - ctx.measureText(words.join("")).width) / spaceWidth;
  const perGap = Math.floor(spare / gaps);
  if (spare < 1) return trimmed;
  return words.join(spaceChar.repeat(perGap));
}

function wrapLines(options: {
  ctx: CanvasRenderingContext2D;
  text: string;
  justify: boolean;
  width: number;
}): string[] {
  const { ctx, text, justify, width } = options;
  const measured = new Map<string, number>();
  const measure = (value: string) => {
    let cached = measured.get(value);
    if (cached === undefined) {
      cached = ctx.measureText(value).width;
      measured.set(value, cached);
    }
    return cached;
  };

  const lines: string[] = [];
  const paragraphs = text.split("\n");
  const hairSpace = justify ? measure("\u200a") : 0;
  let fit = 0;
  let steps = 0;

  for (const paragraph of paragraphs) {
    let remaining = paragraph;
    let remainingWidth = measure(remaining);
    if (remainingWidth <= width) {
      lines.push(remaining);
      continue;
    }

    const length = remaining.length;
    while (remainingWidth > width) {
      steps += 1;
      let cut = fit;
      let cutWidth = cut === 0 ? 0 : measure(remaining.substring(0, cut));
      if (cutWidth < width) {
        while (cutWidth < width && cut < length) {
          cut += 1;
          cutWidth = measure(remaining.substring(0, cut));
          if (cut === length) break;
        }
      } else if (cutWidth > width) {
        while (cutWidth > width && cut !== 0 && cut !== 1) {
          cut = Math.max(1, cut - 1);
          cutWidth = measure(remaining.substring(0, cut));
        }
      }
      fit = Math.round(fit + (cut - fit) / steps);
      cut -= 1;
      if (cut > 0) {
        let space = cut;
        if (remaining.substring(space, space + 1) !== " ") {
          while (remaining.substring(space, space + 1) !== " " && space >= 0) {
            space -= 1;
          }
          if (space > 0) cut = space;
        }
      }
      if (cut === 0) cut = 1;
      const piece = remaining.substring(0, cut);
      lines.push(
        justify
          ? justifyLine({ ctx, line: piece, spaceWidth: hairSpace, spaceChar: "\u200a", width })
          : piece,
      );
      remaining = remaining.substring(cut);
      remainingWidth = measure(remaining);
    }
    if (remainingWidth > 0) {
      lines.push(
        justify
          ? justifyLine({ ctx, line: remaining, spaceWidth: hairSpace, spaceChar: "\u200a", width })
          : remaining,
      );
    }
  }
  return lines;
}

function measureLineHeight(ctx: CanvasRenderingContext2D, text: string, font: string): number {
  const baseline = ctx.textBaseline;
  const previousFont = ctx.font;
  ctx.textBaseline = "bottom";
  ctx.font = font;
  const { actualBoundingBoxAscent } = ctx.measureText(text);
  ctx.textBaseline = baseline;
  ctx.font = previousFont;
  return actualBoundingBoxAscent;
}

export function drawText(
  ctx: CanvasRenderingContext2D,
  text: string,
  options: TextDrawOptions,
): { height: number } {
  const {
    width,
    height,
    x,
    y: top,
    fontSize,
    align = "center",
    vAlign = "middle",
    font: fontFamily = "Arial",
    fontStyle = "",
    fontVariant = "",
    fontWeight = "",
    justify = false,
    debug = false,
  } = options;

  if (width <= 0 || height <= 0 || fontSize <= 0) return { height: 0 };

  const right = x + width;
  const bottom = top + height;
  // The shipped text node presets `ctx.font` to `textSize/2` **pt** and the
  // shared draw helper leaves that size in place; the reference canvas logs
  // "30px SourceSansPro" for a textSize of 45. Using `fontSize` px made every
  // text item 1.5x too large.
  const font = `${fontStyle} ${fontVariant} ${fontWeight} ${fontSize / 2}pt ${fontFamily}`;
  ctx.font = font;

  let textX: number;
  let baselineY = top + height / 2 + fontSize / 2;
  if (align === "right") {
    textX = right;
    ctx.textAlign = "right";
  } else if (align === "left") {
    textX = x;
    ctx.textAlign = "left";
  } else {
    textX = x + width / 2;
    ctx.textAlign = "center";
  }

  const lines = wrapLines({ ctx, text, justify, width });
  const lineHeight = options.lineHeight
    ? options.lineHeight
    : measureLineHeight(ctx, "M", font);
  const totalExtra = lineHeight * (lines.length - 1);
  const middle = totalExtra / 2;

  let markerY = top;
  if (vAlign === "top") {
    ctx.textBaseline = "top";
    baselineY = top;
  } else if (vAlign === "bottom") {
    ctx.textBaseline = "bottom";
    baselineY = bottom - totalExtra;
    markerY = bottom;
  } else {
    ctx.textBaseline = "bottom";
    markerY = top + height / 2;
    baselineY -= middle;
  }

  for (let line of lines) {
    line = line.trim();
    ctx.fillText(line, textX, baselineY);
    baselineY += lineHeight;
  }

  if (debug) {
    const color = "#0C8CE9";
    ctx.lineWidth = 1;
    ctx.strokeStyle = color;
    ctx.strokeRect(x, top, width, height);
    ctx.lineWidth = 1;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(textX, top);
    ctx.lineTo(textX, bottom);
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, markerY);
    ctx.lineTo(right, markerY);
    ctx.stroke();
  }

  return { height: totalExtra + lineHeight };
}
