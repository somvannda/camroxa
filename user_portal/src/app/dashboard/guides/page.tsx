"use client";

import { GuidesDeck } from "./guides-deck";

export default function DashboardGuidesPage() {
  return (
    <div className="-m-1 flex h-[calc(100vh-7.5rem)] min-h-[28rem] flex-col sm:h-[calc(100vh-6.5rem)]">
      <GuidesDeck />
    </div>
  );
}
