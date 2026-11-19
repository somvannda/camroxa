import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import logoUrl from "../../assets/brand/camxora-logo.svg";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Icon } from "../../components/icon";
import type { UpdateCheckResult, UpdateOffer } from "../../../electron/shared/types";

function hasBridge(): boolean {
  return Boolean(window.camxora?.updates);
}

async function openOffer(offer: UpdateOffer): Promise<void> {
  if (!hasBridge()) return;
  await window.camxora.updates.open(offer);
}

export function UpdateGate({ children }: { children: ReactNode }) {
  const [dismissed, setDismissed] = useState(false);
  const check = useQuery<UpdateCheckResult>({
    queryKey: ["update-check"],
    queryFn: async () => {
      if (!hasBridge()) return { currentVersion: "", offer: null };
      const result = await window.camxora.updates.check();
      return result.ok ? result.data : { currentVersion: "", offer: null, message: result.error.message };
    },
    retry: 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const offer = check.data?.offer ?? null;
  if (!offer) return <>{children}</>;

  if (offer.mandatory) {
    return (
      <div className="flex h-full items-center justify-center bg-bg p-8" role="alert">
        <Card className="w-full max-w-xl p-6">
          <div className="flex items-center gap-3">
            <img src={logoUrl} alt="" className="h-9 w-9 rounded-[8px]" />
            <div>
              <p className="text-caption text-text-muted">CAMXORA</p>
              <h1 className="text-subhead font-semibold text-text-primary">Update required</h1>
            </div>
          </div>
          <p className="mt-4 text-body text-text-secondary">
            Camxora {offer.version} is required to continue. Your projects and local files are
            safe.
          </p>
          {offer.notes ? (
            <p className="mt-3 rounded-control border border-border bg-surface-2 p-3 text-body-sm text-text-secondary">
              {offer.notes}
            </p>
          ) : null}
          <div className="mt-5 flex items-center gap-2">
            {offer.url ? (
              <Button variant="primary" onClick={() => void openOffer(offer)}>
                <Icon name="fa-download" size={14} />
                Download update
              </Button>
            ) : (
              <span className="text-body-sm text-text-muted">
                No download link is published yet. Contact support.
              </span>
            )}
            <Button variant="ghost" onClick={() => window.camxora?.window?.close?.()}>
              Quit
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (dismissed) return <>{children}</>;

  return (
    <>
      {children}
      <div className="fixed bottom-10 right-4 z-50 w-[340px]">
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <Icon name="fa-circle-up" size={16} className="mt-0.5 text-accent" />
            <div className="min-w-0 flex-1">
              <p className="text-body-sm font-medium text-text-primary">
                Camxora {offer.version} is available
              </p>
              <p className="mt-0.5 text-meta text-text-secondary">
                Update when you are between projects.
              </p>
              <div className="mt-3 flex items-center gap-2">
                {offer.url ? (
                  <Button variant="primary" className="h-8 px-3" onClick={() => void openOffer(offer)}>
                    Download
                  </Button>
                ) : null}
                <Button variant="ghost" className="h-8 px-2" onClick={() => setDismissed(true)}>
                  Later
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}
