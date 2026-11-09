import type { Metadata } from "next";
import { CreatorPublicView } from "@/components/CreatorPublicView";

type CreatorPageProps = {
  params: Promise<{ handle: string }>;
};

export async function generateMetadata({ params }: CreatorPageProps): Promise<Metadata> {
  const { handle } = await params;
  return {
    title: `@${handle} — Camxora Creator`,
    description: `Listen to @${handle} on Camxora.`,
  };
}

export default async function CreatorPage({ params }: CreatorPageProps) {
  const { handle } = await params;
  return <CreatorPublicView handle={handle} />;
}
