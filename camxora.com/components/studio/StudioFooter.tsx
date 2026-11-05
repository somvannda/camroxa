"use client";

import Link from "next/link";

import { Icon } from "@/components/Icon";
import { StudioLearn } from "@/components/studio/StudioLearn";

/**
 * Editor footer: view tools (still stubs), the selected track's effect chain, and the
 * view/zoom/library controls plus the Learn menu. Extracted from the shell (roadmap G15).
 */

export type StudioFooterProps = {
  chain: string[];
  hasTrack: boolean;
  loop: boolean;
  onLoop: () => void;
  onZoomOut: () => void;
  onZoomFit: () => void;
  onZoomIn: () => void;
  onSearch: () => void;
  onToggleLibrary: () => void;
  whatsThis: boolean;
  onWhatsThis: (next: boolean) => void;
};

export function StudioFooter(props: StudioFooterProps) {
  const {
    chain,
    hasTrack,
    loop,
    onLoop,
    onZoomOut,
    onZoomFit,
    onZoomIn,
    onSearch,
    onToggleLibrary,
    whatsThis,
    onWhatsThis,
  } = props;

  return (
    <footer className="se-foot">
      <div className="se-foot-tools">
        <button type="button" className="se-icon" disabled aria-label="Tools (not wired)"><Icon name="fa-sliders" /></button>
        <button type="button" className="se-icon" disabled aria-label="Draw (not wired)"><Icon name="fa-pen" /></button>
        <button type="button" className="se-icon" disabled aria-label="List (not wired)"><Icon name="fa-bars" /></button>
        <button type="button" className="se-icon" disabled aria-label="Microphone (not wired)"><Icon name="fa-microphone" /></button>
      </div>

      <div className="se-chain">
        {hasTrack && chain.length > 0 ? (
          chain.map((pluginId) => (
            <span key={pluginId} className="se-chain-chip">{pluginId}</span>
          ))
        ) : (
          <span className="se-foot-note">No effects on this track yet.</span>
        )}
        <button type="button" className="se-chain-add" disabled aria-label="Add effect (use the dock above)">
          <Icon name="fa-plus" />
        </button>
      </div>

      <div className="se-foot-right">
        <Link className="se-icon" href="/studio" aria-label="All projects"><Icon name="fa-folder" /></Link>
        <button type="button" className="se-icon" aria-label="Search library" onClick={onSearch}><Icon name="fa-magnifying-glass" /></button>
        <button type="button" className="se-icon" onClick={onZoomOut} aria-label="Zoom out" data-help="zoom"><Icon name="fa-magnifying-glass-minus" /></button>
        <button type="button" className="se-icon" onClick={onZoomFit} aria-label="Fit to content" data-help="zoom"><Icon name="fa-maximize" /></button>
        <button type="button" className="se-icon" onClick={onZoomIn} aria-label="Zoom in" data-help="zoom"><Icon name="fa-magnifying-glass-plus" /></button>
        <button type="button" className="se-icon" onClick={onToggleLibrary} aria-label="Toggle library" data-help="library"><Icon name="fa-table-columns" /></button>
        <button type="button" className={`se-icon${loop ? " on" : ""}`} onClick={onLoop} aria-label="Loop" aria-pressed={loop} data-help="loop"><Icon name="fa-repeat" /></button>
        <StudioLearn whatsThis={whatsThis} onWhatsThis={onWhatsThis} />
      </div>
    </footer>
  );
}
