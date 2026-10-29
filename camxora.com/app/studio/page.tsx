import type { Metadata } from "next";
import { Suspense } from "react";

import { StudioHeader } from "@/components/StudioHeader";
import { StudioLanding } from "@/components/StudioLanding";

export const metadata: Metadata = {
  title: "Studio",
};

export default function StudioPage() {
  return (
    <div className="st-page">
      <StudioHeader />
      <Suspense fallback={null}>
        <StudioLanding />
      </Suspense>
    </div>
  );
}
