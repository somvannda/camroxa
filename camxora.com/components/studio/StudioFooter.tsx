"use client";

import Link from "next/link";

import { Icon } from "@/components/Icon";
import { StudioLearn } from "@/components/studio/StudioLearn";
import { getPlugin } from "@/lib/studio-plugins";

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
  /** S29: the take-lanes band is open. */
  takeLanesOpen?: boolean;
  onToggleTakeLanes?: () => void;
  /** Track automation band is open. */
  automationOpen?: boolean;
  onToggleAutomation?: () => void;
  /** Reference footer tools: Plugins and Clip editor share the bottom panel. */
  onShowPlugins?: () => void;
  onShowClipEditor?: () => void;
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
    takeLanesOpen = false,
    onToggleTakeLanes,
    automationOpen = false,
    onToggleAutomation,
    onShowPlugins,
    onShowClipEditor,
  } = props;

  return (
    <footer className="se-foot">
      <div className="se-foot-tools">
        <span className="se-foot-group">
          <button
            type="button"
            className="se-icon"
            aria-label="Plugins"
            title="Show the selected track's plugins"
            disabled={!hasTrack}
            onClick={() => onShowPlugins?.()}
          >
            <Icon name="fa-sliders" />
          </button>
          <button
            type="button"
            className={`se-icon${automationOpen ? " on" : ""}`}
            aria-label="Automation"
            aria-pressed={automationOpen}
            disabled={!hasTrack}
            onClick={() => onToggleAutomation?.()}
          >
            <Icon name="fa-bezier-curve" />
          </button>
          <button
            type="button"
            className="se-icon"
            aria-label="Clip editor"
            title="Edit the selected clip"
            onClick={() => onShowClipEditor?.()}
          >
            <Icon name="fa-wave-square" />
          </button>
          <button
            type="button"
            className={`se-icon${takeLanesOpen ? " on" : ""}`}
            aria-label="Take lanes"
            aria-pressed={takeLanesOpen}
            onClick={() => onToggleTakeLanes?.()}
          >
            <Icon name="fa-bars" />
          </button>
        </span>
      </div>

      <div className="se-chain">
        {hasTrack && chain.length > 0 ? (
          chain.map((pluginId) => (
            <span key={pluginId} className="se-chain-chip" data-plugin={pluginId}>{getPlugin(pluginId)?.name ?? pluginId}</span>
          ))
        ) : null}
        <button
          type="button"
          className={`se-chain-add${chain.length > 0 ? " compact" : ""}`}
          disabled
          aria-label="Add Track Effects (use the dock above)"
          title="Effects are added in the dock above the footer"
        >
          <Icon name="fa-plus" />
          {chain.length === 0 ? "Add Track Effects" : null}
        </button>
      </div>

      <div className="se-foot-right">
        <span className="se-foot-group">
          <Link className="se-icon" href="/studio" aria-label="All projects"><Icon name="fa-folder" /></Link>
        </span>
        <span className="se-foot-group">
          <button type="button" className="se-icon" aria-label="Search library" onClick={onSearch}><Icon name="fa-magnifying-glass" /></button>
          <button type="button" className="se-icon" onClick={onZoomOut} aria-label="Zoom out" data-help="zoom"><Icon name="fa-magnifying-glass-minus" /></button>
          <button type="button" className="se-icon" onClick={onZoomFit} aria-label="Fit to content" data-help="zoom"><Icon name="fa-maximize" /></button>
          <button type="button" className="se-icon" onClick={onZoomIn} aria-label="Zoom in" data-help="zoom"><Icon name="fa-magnifying-glass-plus" /></button>
        </span>
        <button type="button" className="se-icon" onClick={onToggleLibrary} aria-label="Toggle library" data-help="library"><Icon name="fa-table-columns" /></button>
        <button type="button" className={`se-icon${loop ? " on" : ""}`} onClick={onLoop} aria-label="Loop" aria-pressed={loop} data-help="loop"><Icon name="fa-repeat" /></button>
        <StudioLearn whatsThis={whatsThis} onWhatsThis={onWhatsThis} />
      </div>
    </footer>
  );
}
