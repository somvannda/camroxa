"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import {
  CreatorButton,
  CreatorButtonLink,
  CreatorCheckbox,
  CreatorField,
  CREATOR_NAV_ITEMS,
  CreatorHeader,
  CreatorInput,
  CreatorPage,
  CreatorPanel,
  CreatorSubnav,
  CreatorSelect,
  CreatorStatus,
  CreatorTextarea,
  CreatorToast,
  useCreatorToast,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
import {
  CreatorApiError,
  fetchProgramStatus,
  submitApplication,
  submitVerification,
  withdrawApplication,
  type CreatorProgramStatus,
  type CreatorVerification,
} from "@/lib/creator-api";

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  in_review: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  draft: "Draft",
};

function statusTone(status: string): "neutral" | "review" | "live" | "danger" {
  if (status === "approved") return "live";
  if (["submitted", "in_review", "changes_requested"].includes(status)) return "review";
  if (status === "rejected") return "danger";
  return "neutral";
}

export function CreatorVerificationView() {
  const [status, setStatus] = useState<CreatorProgramStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [error, setError] = useState("");
  const { toast, showToast, dismiss } = useCreatorToast();
  const [pitch, setPitch] = useState("");
  const [link, setLink] = useState("");
  const [rights, setRights] = useState(false);
  const [evidenceKind, setEvidenceKind] = useState<CreatorVerification["kind"]>("identity");
  const [evidenceRef, setEvidenceRef] = useState("");
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function refresh() {
    setStatus(await fetchProgramStatus());
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchProgramStatus()
      .then((data) => {
        if (active) setStatus(data);
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof CreatorApiError && cause.status === 401) {
          setUnauthorized(true);
        } else {
          setError(cause instanceof Error ? cause.message : "Could not load verification status");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function onApply(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setFieldErrors({});
    try {
      await submitApplication({
        pitch: pitch.trim(),
        links: [{ label: "External link", url: link.trim() }],
        rights_attested: rights,
        requested_tier: "verified",
      });
      showToast("Badge request submitted. You can keep publishing while we review.");
      setPitch("");
      setLink("");
      setRights(false);
      await refresh();
    } catch (cause) {
      if (cause instanceof CreatorApiError) setFieldErrors(cause.fields);
      setError(cause instanceof Error ? cause.message : "Could not submit application");
    } finally {
      setSaving(false);
    }
  }

  async function onWithdraw() {
    setSaving(true);
    setError("");
    setFieldErrors({});
    try {
      await withdrawApplication();
      showToast("Application withdrawn.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not withdraw application");
    } finally {
      setSaving(false);
    }
  }

  async function onVerification(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setFieldErrors({});
    try {
      await submitVerification({ kind: evidenceKind, evidence_ref: evidenceRef.trim() });
      showToast("Verification evidence submitted.");
      setEvidenceRef("");
      await refresh();
    } catch (cause) {
      if (cause instanceof CreatorApiError) setFieldErrors(cause.fields);
      setError(cause instanceof Error ? cause.message : "Could not submit evidence");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Verification" />
        <div className={styles.skeletonPanel}>
          <div className={styles.skeleton} style={{ width: 260, height: 28 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 96 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 220 }} />
        </div>
      </CreatorPage>
    );
  }

  if (unauthorized) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Verification" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Sign in to continue</p>
            <p className={styles.emptyBody}>Request the badge or complete payout identity verification.</p>
            <div>
              <CreatorButtonLink href="/login?next=/creator/verification" variant="primary">
                <Icon name="fa-right-to-bracket" /> Sign in
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  if (!status?.profile) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Verification" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Claim a creator page first</p>
            <p className={styles.emptyBody}>You need a creator profile before you can request the badge.</p>
            <div>
              <CreatorButtonLink href="/creator" variant="primary">
                <Icon name="fa-microphone-lines" /> Open Creator Studio
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  const application = status.application;
  const canApply =
    !application || application.status === "changes_requested" || application.status === "rejected";

  return (
    <CreatorPage>
      <CreatorHeader
        meta="Creator Studio"
        title="Verification"
        description="Optional: request the Verified Creator badge. You can publish without it."
        actions={
          <>
            <CreatorButtonLink href="/creator" variant="ghost">
              <Icon name="fa-arrow-left" /> Back to Studio
            </CreatorButtonLink>
            <CreatorButtonLink href={`/creators/${status.profile.handle}`} variant="ghost">
              <Icon name="fa-arrow-up-right-from-square" /> View public page
            </CreatorButtonLink>
          </>
        }
      />

      <CreatorSubnav items={CREATOR_NAV_ITEMS} />

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <CreatorMetrics
        items={[
          { label: "Current tier", value: status.profile.tier },
          { label: "Badge request", value: application ? STATUS_LABELS[application.status] ?? application.status : "Not requested" },
          { label: "Active badges", value: status.badges.length },
          { label: "Evidence items", value: status.verifications.length },
        ]}
      />

      {application ? (
        <CreatorPanel title="Badge request" meta={`Version ${application.version}`}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div>
              <CreatorStatus
                label={STATUS_LABELS[application.status] ?? application.status}
                tone={statusTone(application.status)}
              />
              <p className={styles.rowMeta}>
                {application.submitted_at ? `Submitted ${formatDate(application.submitted_at)}` : "Not submitted"}
                {application.sla_due_at ? ` · review by ${formatDate(application.sla_due_at)}` : ""}
              </p>
            </div>
            {["submitted", "in_review", "changes_requested"].includes(application.status) ? (
              <CreatorButton variant="secondary" type="button" onClick={onWithdraw} disabled={saving}>
                <Icon name="fa-rotate-left" /> Withdraw request
              </CreatorButton>
            ) : null}
          </div>
          {application.decision_reason ? (
            <p className={styles.rowMeta}>Reviewer note: {application.decision_reason}</p>
          ) : null}
        </CreatorPanel>
      ) : null}

      {canApply ? (
        <CreatorPanel
          title={application?.status === "changes_requested" ? "Update and resubmit" : "Request the Verified badge"}
          className={styles.sectionGap}
        >
          <form className={styles.form} onSubmit={onApply}>
            <CreatorField
              label="Why should we verify you? (50–500 characters)"
              htmlFor="app-pitch"
              hint={`${pitch.length}/500`}
            >
              <CreatorTextarea
                id="app-pitch"
                value={pitch}
                onChange={(event) => setPitch(event.target.value)}
                minLength={50}
                maxLength={500}
                rows={4}
                required
                placeholder="Tell us about your music, your audience, and what you are building."
              />
            </CreatorField>
            <CreatorField label="External link" htmlFor="app-link" error={fieldErrors.links}>
              <CreatorInput
                id="app-link"
                value={link}
                onChange={(event) => setLink(event.target.value)}
                placeholder="https://youtube.com/@yourchannel"
                required
              />
            </CreatorField>
            <CreatorCheckbox
              id="app-rights"
              checked={rights}
              onCheckedChange={setRights}
              label="I own or have cleared the rights to my tracks, samples, vocals, lyrics, and artwork."
            />
            <div>
              <CreatorButton type="submit" disabled={saving || !rights}>
                <Icon name="fa-paper-plane" /> {saving ? "Submitting…" : "Request badge"}
              </CreatorButton>
            </div>
          </form>
        </CreatorPanel>
      ) : null}

      <CreatorPanel
        title="Verification evidence"
        meta="Optional · encrypted"
        className={styles.sectionGap}
      >
        <p className={styles.emptyBody} style={{ marginBottom: 20 }}>
          Optional evidence to support the badge request. Payout identity verification is separate and lives in Payouts.
        </p>
        <div className={styles.actions} style={{ marginBottom: 20 }}>
          <CreatorButtonLink href="/creator/payouts" variant="secondary">
            <Icon name="fa-shield-halved" /> Open payouts
          </CreatorButtonLink>
        </div>
        <form className={styles.form} onSubmit={onVerification}>
          <CreatorField label="Evidence type" htmlFor="evidence-kind" error={fieldErrors.kind}>
            <CreatorSelect
              id="evidence-kind"
              value={evidenceKind}
              onValueChange={(value) => setEvidenceKind(value as CreatorVerification["kind"])}
              options={[
                { value: "identity", label: "Identity document" },
                { value: "authenticity", label: "Authenticity / social proof" },
                { value: "business", label: "Business registration" },
                { value: "voice_consent", label: "Voice consent" },
              ]}
              ariaLabel="Evidence type"
            />
          </CreatorField>
          <CreatorField label="Evidence reference" htmlFor="evidence-ref" error={fieldErrors.evidence_ref}>
            <CreatorInput
              id="evidence-ref"
              value={evidenceRef}
              onChange={(event) => setEvidenceRef(event.target.value)}
              placeholder="Secure upload reference or https:// link"
              required
            />
          </CreatorField>
          <div>
            <CreatorButton variant="secondary" type="submit" disabled={saving || !evidenceRef.trim()}>
              <Icon name="fa-upload" /> Submit evidence
            </CreatorButton>
          </div>
        </form>
      </CreatorPanel>

      <CreatorPanel title="Evidence history" className={styles.sectionGap}>
        {status.verifications.length === 0 ? (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>No evidence submitted yet</p>
            <p className={styles.emptyBody}>Identity, authenticity, business, and voice-consent evidence will appear here.</p>
          </div>
        ) : (
          <div className={styles.list}>
            {status.verifications.map((item) => (
              <div className={styles.row} key={item.id}>
                <div>
                  <p className={styles.rowTitle}>{item.kind.replace("_", " ")}</p>
                  <p className={styles.rowMeta}>
                    Submitted {formatDate(item.created_at)}
                    {item.reviewed_at ? ` · reviewed ${formatDate(item.reviewed_at)}` : ""}
                  </p>
                </div>
                <CreatorStatus
                  label={item.status}
                  tone={item.status === "approved" ? "live" : item.status === "rejected" ? "danger" : "review"}
                />
              </div>
            ))}
          </div>
        )}
      </CreatorPanel>
      <CreatorToast toast={toast} onDismiss={dismiss} />
    </CreatorPage>
  );
}
