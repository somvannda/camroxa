import { parseReleaseNotes } from "@/lib/release-notes";

type ReleaseNotesContentProps = {
  content: string;
  className?: string;
};

export function ReleaseNotesContent({ content, className = "" }: ReleaseNotesContentProps) {
  const parsed = parseReleaseNotes(content);

  if (parsed.sections.length === 0) {
    return (
      <div className={`whitespace-pre-wrap text-base leading-8 text-slate-200/80 md:text-lg ${className}`}>
        {content.trim()}
      </div>
    );
  }

  return (
    <div className={`space-y-8 ${className}`}>
      {parsed.versionHeading ? (
        <div className="text-sm uppercase tracking-[0.18em] text-slate-400">{parsed.versionHeading}</div>
      ) : null}

      {parsed.sections.map((section) => (
        <section key={section.title}>
          <h2 className="font-display text-2xl font-semibold tracking-[-0.04em] text-white md:text-3xl">
            {section.title}
          </h2>
          <ul className="mt-4 space-y-3 text-base leading-8 text-slate-200/80 md:text-lg">
            {section.items.map((item) => (
              <li key={item} className="flex gap-3">
                <span aria-hidden className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-300/80" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
