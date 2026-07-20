import {
  MarketingFooter,
  MarketingHeader,
  getUserPortalBaseUrl,
} from "@/components/marketing/site-chrome";

type ContentPageShellProps = {
  eyebrow: string;
  title: string;
  description: React.ReactNode;
  children: React.ReactNode;
  aside?: React.ReactNode;
};

export function ContentPageShell(props: ContentPageShellProps) {
  const userPortalBaseUrl = getUserPortalBaseUrl();

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(1000px_circle_at_12%_0%,rgba(168,85,247,0.14),transparent_34%),radial-gradient(860px_circle_at_88%_14%,rgba(139,92,246,0.16),transparent_32%),radial-gradient(740px_circle_at_80%_78%,rgba(217,70,239,0.08),transparent_24%)]" />

      <MarketingHeader userPortalBaseUrl={userPortalBaseUrl} />

      <main className="relative mx-auto flex w-full max-w-7xl flex-1 flex-col gap-16 px-6 py-14 md:px-10 md:py-20">
        <section className="grid gap-10 border-b border-white/8 pb-14 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
          <div className="max-w-4xl">
            <div className="inline-flex w-fit items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-100/78">
              {props.eyebrow}
            </div>

            <h1 className="mt-6 font-display text-4xl font-semibold tracking-[-0.06em] text-white md:text-6xl">
              {props.title}
            </h1>
            <div className="mt-5 max-w-3xl space-y-4 text-base leading-8 text-slate-200/70 md:text-lg">
              {typeof props.description === "string" ? (
                <p>{props.description}</p>
              ) : (
                props.description
              )}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6">
            {props.aside ?? (
              <div className="space-y-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.22em] text-slate-400">
                    Why Camxora
                  </div>
                  <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
                    Faceless desktop studio, end to end.
                  </div>
                </div>
                <p className="text-sm leading-6 text-slate-200/72">
                  Lyrics to YouTube-ready video in one Windows studio — with honest upload roadmap.
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="flex-1 space-y-16">
          {props.children}
        </section>
      </main>

      <MarketingFooter userPortalBaseUrl={userPortalBaseUrl} />
    </div>
  );
}
