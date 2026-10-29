import type { Metadata } from "next";
import { Suspense } from "react";

import { StudioLanding } from "@/components/StudioLanding";

export const metadata: Metadata = {
  title: "Studio",
};

export default function StudioPage() {
  return (
    <Suspense fallback={null}>
      <StudioLanding />
    </Suspense>
  );
}
