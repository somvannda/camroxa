import React from "react";
import { LeftPanel } from "./LeftPanel";
import { CenterPreview } from "./CenterPreview";
import { RightPanel } from "./RightPanel";

export const SpectrumEditor: React.FC = () => {
  return (
    <div className="flex h-full w-full overflow-hidden bg-slate-950 text-slate-200">
      <LeftPanel />
      <CenterPreview />
      <RightPanel />
    </div>
  );
};
