"use client";

import { Icon } from "@/components/Icon";
import { Waveform } from "@/components/studio/Waveform";

/**
 * Take lanes (S29).
 *
 * The footer's Take lanes control opens a full-width band under the arrangement. The
 * band is driven by the selected clip: a clip that was generated over more than once
 * stacks its takes (newest on top, active one bright with a tick), every other clip
 * shows the captured empty copy.
 */

export type TakeLaneTake = {
  id: string;
  title?: string;
  audioUrl?: string | null;
  duration?: number;
  active?: boolean;
};

export function StudioTakeLanes({
  takes,
  color,
  onClose,
  onActivate,
}: {
  takes: TakeLaneTake[] | null;
  color: string;
  onClose: () => void;
  onActivate: (takeId: string) => void;
}) {
  const rows = takes ?? [];
  return (
    <section className="se-takes" aria-label="Take lanes">
      <button type="button" className="se-icon se-takes-close" aria-label="Close take lanes" onClick={onClose}>
        <Icon name="fa-xmark" />
      </button>
      {rows.length === 0 ? (
        <p className="se-takes-empty">Create a clip to see alternate takes here</p>
      ) : (
        <ul className="se-takes-list">
          {rows.map((take, position) => {
            const number = rows.length - position;
            const active = Boolean(take.active);
            return (
              <li key={take.id} className={`se-take${active ? " is-active" : ""}`}>
                <span className="se-take-gutter">
                  {active ? <Icon name="fa-check" className="se-take-tick" /> : null}
                  <span className="se-take-number">{number}</span>
                </span>
                <button
                  type="button"
                  className="se-take-clip"
                  style={{ background: color }}
                  aria-label={`Use take ${number}`}
                  aria-pressed={active}
                  onClick={() => onActivate(take.id)}
                >
                  <span className="se-take-title">{take.title || "Take"}</span>
                  <Waveform
                    url={take.audioUrl ?? undefined}
                    width={360}
                    height={22}
                    className="se-take-wave"
                    label={`${take.title || "Take"} take waveform`}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
