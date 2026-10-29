import type { Metadata } from "next";
import { LibraryView } from "@/components/LibraryView";

export const metadata: Metadata = {
  title: "Trash",
};

/** Suno opens Trash at `/me/trash`; ours is a Library section at this route. */
export default function LibraryTrashPage() {
  return <LibraryView initialTab="trash" />;
}
