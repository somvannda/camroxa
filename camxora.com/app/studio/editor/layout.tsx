export default function StudioEditorLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <div className="studio-standalone">{children}</div>;
}
