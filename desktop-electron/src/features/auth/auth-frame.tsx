import type { ReactNode } from "react";
import heroUrl from "../../assets/brand/auth-hero.png";
import { Footer } from "../../shell/footer";
import { TitleBar } from "../../shell/titlebar";

/**
 * Auth chrome, aligned with camxora.com's sign-in page: a hero visual on the
 * left and a narrow auth panel on the right. The desktop keeps its own title
 * bar so the frameless window still has window controls.
 *
 * `solo` keeps the same card treatment without the marketing visual; gates and
 * recovery screens use it so they stay focused.
 */
export function AuthFrame({
  children,
  variant = "split",
}: {
  children: ReactNode;
  variant?: "split" | "solo";
}) {
  const split = variant === "split";

  return (
    <div className="flex h-full flex-col bg-bg">
      <TitleBar />

      <div className={split ? "grid min-h-0 flex-1 lg:grid-cols-[1.05fr_0.95fr]" : "min-h-0 flex-1"}>
        {split ? (
          <div className="relative hidden overflow-hidden lg:block">
            <img
              src={heroUrl}
              alt="Singer with headphones in neon light"
              className="absolute inset-0 h-full w-full object-cover object-[60%_25%] opacity-80"
            />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,10,19,0.25),rgba(7,10,19,0.9))]" />
            <div className="relative z-10 flex h-full flex-col justify-end p-11">
              <p className="text-caption font-semibold uppercase tracking-[0.16em] text-text-muted">
                Camxora
              </p>
              <h2 className="mt-2 max-w-[420px] text-[clamp(28px,3.4vw,46px)] font-semibold leading-[1.03] tracking-[-0.05em] text-text-primary">
                Create. Discover.
                <br />
                Enjoy AI Music.
              </h2>
              <p className="mt-2 max-w-[400px] text-body-sm leading-6 text-text-muted">
                Listen to what creators are making, then make the next track everyone plays.
              </p>
            </div>
          </div>
        ) : null}

        <div
          className={
            split
              ? "flex min-h-0 items-center justify-center overflow-y-auto px-6 py-10"
              : "flex min-h-0 items-center justify-center overflow-y-auto p-6"
          }
        >
          <div className="w-full max-w-[420px]">{children}</div>
        </div>
      </div>

      <Footer variant="auth" />
    </div>
  );
}
