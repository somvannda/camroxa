"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
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

export function CreatorVerificationView() {
  const [status, setStatus] = useState<CreatorProgramStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pitch, setPitch] = useState("");
  const [link, setLink] = useState("");
  const [rights, setRights] = useState(false);
  const [evidenceKind, setEvidenceKind] = useState<CreatorVerification["kind"]>("identity");
  const [evidenceRef, setEvidenceRef] = useState("");
  const [saving, setSaving] = useState(false);

  async function refresh() {
    const data = await fetchProgramStatus();
    setStatus(data);
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
    setSuccess("");
    try {
      await submitApplication({
        pitch: pitch.trim(),
        links: [{ label: "External link", url: link.trim() }],
        rights_attested: rights,
        requested_tier: "verified",
      });
      setSuccess("Application submitted. We review within 3 business days.");
      setPitch("");
      setLink("");
      setRights(false);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit application");
    } finally {
      setSaving(false);
    }
  }

  async function onWithdraw() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await withdrawApplication();
      setSuccess("Application withdrawn.");
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
    setSuccess("");
    try {
      await submitVerification({ kind: evidenceKind, evidence_ref: evidenceRef.trim() });
      setSuccess("Verification evidence submitted.");
      setEvidenceRef("");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit evidence");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="page"><p className="fine" style={{ textAlign: "left" }}>Loading verification…</p></div>;
  }

  if (unauthorized) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-badge-check" /></span>
          <h1>Verification</h1>
          <p>Sign in to apply for Verified Creator status.</p>
          <Link className="btn btn-primary" href="/login?next=/creator/verification">Sign in</Link>
        </div>
      </div>
    );
  }

  if (!status?.profile) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-user-plus" /></span>
          <h1>Claim a creator page first</h1>
          <p>You need a creator profile before you can apply for verification.</p>
          <Link className="btn btn-primary" href="/creator">Open Creator Studio</Link>
        </div>
      </div>
    );
  }

  const application = status.application;
  const canApply =
    !application || application.status === "changes_requested" || application.status === "rejected";

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="fine" style={{ margin: 0 }}>Creator Studio / Verification</p>
          <h1>Verification</h1>
          <p>Apply for the Verified Creator badge and track your review.</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/creator">Back to Studio</Link>
          <Link className="btn btn-ghost" href={`/creators/${status.profile.handle}`}>View public page</Link>
        </div>
      </div>

      {error ? <p className="fine" style={{ color: "#f87171" }} role="alert">{error}</p> : null}
      {success ? <p className="fine" style={{ color: "#4ade80" }} role="status">{success}</p> : null}

      <CreatorMetrics
        items={[
          { label: "Current tier", value: status.profile.tier },
          { label: "Application", value: application ? STATUS_LABELS[application.status] ?? application.status : "Not applied" },
          { label: "Active badges", value: status.badges.length },
          { label: "Evidence items", value: status.verifications.length },
        ]}
      />

      {application ? (
        <section className="panel">
          <div className="sec-head">
            <h2>Application status</h2>
            <span className="fine">Version {application.version}</span>
          </div>
          <p>
            <strong>{STATUS_LABELS[application.status] ?? application.status}</strong>
            {application.submitted_at ? ` · submitted ${formatDate(application.submitted_at)}` : ""}
            {application.sla_due_at ? ` · review by ${formatDate(application.sla_due_at)}` : ""}
          </p>
          {application.decision_reason ? (
            <p className="fine" style={{ textAlign: "left" }}>Reviewer note: {application.decision_reason}</p>
          ) : null}
          {["submitted", "in_review", "changes_requested"].includes(application.status) ? (
            <div className="page-actions" style={{ marginTop: 12 }}>
              <button className="btn btn-ghost" type="button" onClick={onWithdraw} disabled={saving}>
                Withdraw application
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      {canApply ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <div className="sec-head">
            <h2>{application?.status === "changes_requested" ? "Update and resubmit" : "Apply for verification"}</h2>
          </div>
          <form onSubmit={onApply} style={{ display: "grid", gap: 16 }}>
            <div className="auth-field">
              <label htmlFor="app-pitch">Why should we verify you? (50–500 characters)</label>
              <textarea
                id="app-pitch"
                className="auth-input"
                value={pitch}
                onChange={(event) => setPitch(event.target.value)}
                minLength={50}
                maxLength={500}
                rows={4}
                required
                placeholder="Tell us about your music, your audience, and what you are building."
                style={{ minHeight: 110, resize: "vertical" }}
              />
              <span className="fine">{pitch.length}/500</span>
            </div>
            <div className="auth-field">
              <label htmlFor="app-link">External link</label>
              <input
                id="app-link"
                className="auth-input"
                value={link}
                onChange={(event) => setLink(event.target.value)}
                placeholder="https://youtube.com/@yourchannel"
                required
              />
            </div>
            <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={rights}
                onChange={(event) => setRights(event.target.checked)}
                required
              />
              <span className="fine">
                I own or have cleared the rights to my tracks, samples, vocals, lyrics, and artwork.
              </span>
            </label>
            <div className="page-actions">
              <button className="btn btn-primary" type="submit" disabled={saving || !rights}>
                {saving ? "Submitting…" : "Submit application"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="panel" style={{ marginTop: 16 }}>
        <div className="sec-head">
          <h2>Identity evidence</h2>
          <span className="fine">Encrypted and reviewed by a human.</span>
        </div>
        <form onSubmit={onVerification} style={{ display: "grid", gap: 16 }}>
          <div className="auth-field">
            <label htmlFor="evidence-kind">Evidence type</label>
            <select
              id="evidence-kind"
              className="auth-input"
              value={evidenceKind}
              onChange={(event) => setEvidenceKind(event.target.value as CreatorVerification["kind"])}
            >
              <option value="identity">Identity document</option>
              <option value="authenticity">Authenticity / social proof</option>
              <option value="business">Business registration</option>
              <option value="voice_consent">Voice consent</option>
            </select>
          </div>
          <div className="auth-field">
            <label htmlFor="evidence-ref">Evidence reference</label>
            <input
              id="evidence-ref"
              className="auth-input"
              value={evidenceRef}
              onChange={(event) => setEvidenceRef(event.target.value)}
              placeholder="Secure upload reference or https:// link"
              required
            />
          </div>
          <div className="page-actions">
            <button className="btn btn-ghost" type="submit" disabled={saving || !evidenceRef.trim()}>
              Submit evidence
            </button>
          </div>
        </form>
      </section>

      <section className="panel" style={{ marginTop: 16 }}>
        <div className="sec-head"><h2>Evidence history</h2></div>
        {status.verifications.length === 0 ? (
          <p className="fine" style={{ textAlign: "left" }}>No evidence submitted yet.</p>
        ) : (
          <div className="invite-table-wrap">
            <table className="invite-table">
              <thead><tr><th>Type</th><th>Status</th><th>Submitted</th><th>Reviewed</th></tr></thead>
              <tbody>
                {status.verifications.map((item) => (
                  <tr key={item.id}>
                    <td>{item.kind.replace("_", " ")}</td>
                    <td>{item.status}</td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>{formatDate(item.reviewed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
