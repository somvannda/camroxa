import type { Metadata } from "next";
import { Suspense } from "react";

import { StudioHome } from "@/components/studio/StudioHome";
import { StudioMarketing } from "@/components/studio/StudioMarketing";

export const metadata: Metadata = {
  title: "Studio",
};

/**
 * `/studio` — the signed-in home for Studio (spec §56, §62).
 *
 * Signed out, `StudioHome` renders the marketing page instead (§58): the route
 * itself is the auth gate, matching the reference's behaviour of never showing a
 * half-populated chooser to a visitor. Signed in, it lists the user's projects and
 * resumes work straight into `/studio/editor?project=<id>`.
 */
export default function StudioPage() {
  return (
    <Suspense fallback={null}>
      <StudioHome marketing={<StudioMarketing />} />
    </Suspense>
  );
}
