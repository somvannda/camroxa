"use client";

import { useEffect, useState } from "react";

/**
 * Metric parity probe (dev only).
 *
 * "Do we look like the reference?" is answerable only if it is measurable. The
 * captured numbers live in `docs/studio/reference/METRICS.json`; this renders the
 * live measurement beside each one and prints the delta.
 *
 * Enable with `?metrics=1` on the editor. Production builds render nothing.
 */

type Metric = {
  id: string;
  label: string;
  selector: string;
  measure: "height" | "width" | "spacing";
  expected: number;
  tolerance: number;
  spec: string;
  feature: string;
  functional: "wired" | "partial" | "visual";
  note?: string;
};

type Result = Metric & { actual: number | null; delta: number | null; pass: boolean };

function measure(metric: Metric): number | null {
  const nodes = Array.from(document.querySelectorAll(metric.selector));
  if (nodes.length === 0) return null;

  if (metric.measure === "spacing") {
    if (nodes.length < 2) return null;
    const a = nodes[0].getBoundingClientRect().left;
    const b = nodes[1].getBoundingClientRect().left;
    return Math.round(Math.abs(b - a));
  }

  const rect = nodes[0].getBoundingClientRect();
  return Math.round(metric.measure === "height" ? rect.height : rect.width);
}

export function StudioMetricsProbe() {
  const [enabled, setEnabled] = useState(false);
  const [rows, setRows] = useState<Result[]>([]);

  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    if (typeof window === "undefined") return;
    const on = new URLSearchParams(window.location.search).get("metrics") === "1";
    setEnabled(on);
    if (!on) return;

    let cancelled = false;
    void (async () => {
      const response = await fetch("/studio-metrics.json");
      const data = (await response.json()) as { metrics: Metric[] };
      await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
      if (cancelled) return;
      setRows(
        data.metrics.map((metric) => {
          const actual = measure(metric);
          const delta = actual === null ? null : actual - metric.expected;
          return {
            ...metric,
            actual,
            delta,
            pass: delta !== null && Math.abs(delta) <= metric.tolerance,
          };
        })
      );
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!enabled || rows.length === 0) return null;

  const failures = rows.filter((row) => !row.pass).length;
  const wired = rows.filter((row) => row.functional === "wired").length;
  const partial = rows.filter((row) => row.functional === "partial").length;
  const visual = rows.filter((row) => row.functional === "visual").length;

  return (
    <div className="se-metrics" role="dialog" aria-label="Metric parity">
      <div className="se-metrics-head">
        <strong>Metric parity</strong>
        <span>
          {rows.length - failures}/{rows.length} px · {wired} wired · {partial} partial ·{" "}
          {visual} visual
        </span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Ref</th>
            <th>Ours</th>
            <th>Δ</th>
            <th>Feature</th>
            <th>Functionality</th>
            <th>§</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className={row.pass ? "ok" : "off"}>
              <td>{row.label}</td>
              <td>{row.expected}</td>
              <td>{row.actual ?? "—"}</td>
              <td>{row.delta === null ? "—" : row.delta > 0 ? `+${row.delta}` : row.delta}</td>
              <td className="feature">{row.feature}</td>
              <td className={`func ${row.functional}`} title={row.note ?? undefined}>
                {row.functional}
                {row.note ? <em> — {row.note}</em> : null}
              </td>
              <td>{row.spec}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
