import { PlayerProvider } from "@/components/PlayerProvider";

export default function StudioEditorLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <PlayerProvider>
      <div className="studio-standalone">{children}</div>
    </PlayerProvider>
  );
}
