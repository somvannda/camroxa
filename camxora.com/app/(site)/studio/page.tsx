import type { Metadata } from "next";

import { StudioHome } from "@/components/studio/StudioHome";
import { StudioMarketing } from "@/components/studio/StudioMarketing";

export const metadata: Metadata = {
  title: "Camxora Studio",
};

/**
 * `/studio`
 *
 * Signed in: the Studio home (resume, projects, create).
 * Signed out: the public product page.
 *
 * The DAW itself lives at `/studio/editor`, which is chrome-free.
 */
export default function StudioPage() {
  return <StudioHome marketing={<StudioMarketing />} />;
}
