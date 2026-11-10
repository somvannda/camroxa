"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import {
  CreatorButton,
  CreatorButtonLink,
  CreatorField,
  CREATOR_NAV_ITEMS,
  CreatorHeader,
  CreatorInput,
  CreatorPage,
  CreatorPanel,
  CreatorSubnav,
  CreatorSelect,
  CreatorStatus,
  CreatorToast,
  creatorButtonClass,
  useCreatorToast,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
import {
  CreatorApiError,
  fetchPayoutStatus,
  requestPayout,
  savePayoutAccount,
  submitKyc,
  uploadKycDocument,
  type CreatorPayoutStatus,
} from "@/lib/creator-api";

function usd(micros: number): string {
  return `$${(Number(micros || 0) / 1_000_000).toFixed(2)}`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function kycTone(status?: string | null): "neutral" | "review" | "live" | "danger" {
  if (status === "verified") return "live";
  if (status === "pending") return "review";
  if (status === "rejected" || status === "expired") return "danger";
  return "neutral";
}

export function CreatorPayoutsView() {
  const [data, setData] = useState<CreatorPayoutStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const { toast, showToast, dismiss } = useCreatorToast();

  const [legalName, setLegalName] = useState("");
  const [dob, setDob] = useState("");
  const [country, setCountry] = useState("KH");
  const [idType, setIdType] = useState<"passport" | "national_id" | "drivers_license">("national_id");
  const [idLast4, setIdLast4] = useState("");
  const [documentRef, setDocumentRef] = useState("");
  const [selfieRef, setSelfieRef] = useState("");
  const [docNames, setDocNames] = useState<{ id?: string; selfie?: string }>({});
  const [uploadingDoc, setUploadingDoc] = useState<"id" | "selfie" | null>(null);
  const [taxId, setTaxId] = useState("");

  const [method, setMethod] = useState<"aba" | "wing" | "khqr" | "bank" | "paypal" | "wise">("aba");
  const [accountName, setAccountName] = useState("");
  const [accountLast4, setAccountLast4] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [currency, setCurrency] = useState<"USD" | "KHR">("USD");

  async function refresh() {
    setData(await fetchPayoutStatus());
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchPayoutStatus()
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof CreatorApiError && cause.status === 401) {
          setUnauthorized(true);
        } else {
          setError(cause instanceof Error ? cause.message : "Could not load payouts");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function onDocument(kind: "id" | "selfie", file: File) {
    setUploadingDoc(kind);
    setError("");
    setFieldErrors({});
    try {
      const { key } = await uploadKycDocument(kind, file);
      if (kind === "id") {
        setDocumentRef(key);
      } else {
        setSelfieRef(key);
      }
      setDocNames((current) => ({ ...current, [kind]: file.name }));
      showToast(kind === "id" ? "ID document uploaded." : "Selfie uploaded.");
    } catch (cause) {
      if (cause instanceof CreatorApiError) setFieldErrors(cause.fields);
      setError(cause instanceof Error ? cause.message : "Could not upload the document");
    } finally {
      setUploadingDoc(null);
    }
  }

  async function onKyc(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setFieldErrors({});
    try {
      await submitKyc({
        legal_name: legalName.trim(),
        date_of_birth: dob,
        country_code: country.trim().toUpperCase(),
        id_type: idType,
        id_last4: idLast4.trim(),
        id_document_ref: documentRef.trim(),
        selfie_ref: selfieRef.trim() || undefined,
        tax_id: taxId.trim() || undefined,
      });
      showToast("Payout verification submitted. We review it before your first payout.");
      await refresh();
    } catch (cause) {
      if (cause instanceof CreatorApiError) setFieldErrors(cause.fields);
      setError(cause instanceof Error ? cause.message : "Could not submit verification");
    } finally {
      setSaving(false);
    }
  }

  async function onAccount(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setFieldErrors({});
    try {
      await savePayoutAccount({
        method,
        account_name: accountName.trim(),
        account_last4: accountLast4.trim(),
        bank_code: bankCode.trim() || undefined,
        currency,
      });
      showToast("Payout account saved. It needs verification before the first payout.");
      await refresh();
    } catch (cause) {
      if (cause instanceof CreatorApiError) setFieldErrors(cause.fields);
      setError(cause instanceof Error ? cause.message : "Could not save payout account");
    } finally {
      setSaving(false);
    }
  }

  async function onRequest() {
    setSaving(true);
    setError("");
    setFieldErrors({});
    try {
      await requestPayout();
      showToast("Payout requested. Finance reviews it in the next cycle.");
      await refresh();
    } catch (cause) {
      if (cause instanceof CreatorApiError) setFieldErrors(cause.fields);
      setError(cause instanceof Error ? cause.message : "Could not request payout");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Payouts" />
        <div className={styles.skeletonPanel}>
          <div className={styles.skeleton} style={{ width: 220, height: 28 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 72 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 320 }} />
        </div>
      </CreatorPage>
    );
  }

  if (unauthorized) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Payouts" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Sign in to manage payouts</p>
            <p className={styles.emptyBody}>Complete verification once, then request payouts when your balance reaches $20.</p>
            <div>
              <CreatorButtonLink href="/login?next=/creator/payouts" variant="primary">
                <Icon name="fa-right-to-bracket" /> Sign in
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  const balance = data?.balance;
  const kyc = data?.kyc;
  const account = data?.account;
  const canRequest =
    kyc?.status === "verified" &&
    account?.status === "verified" &&
    (balance?.available_micros ?? 0) >= (balance?.min_payout_micros ?? 20_000_000);
  const kycLocked = kyc?.status === "verified" || kyc?.status === "pending";

  return (
    <CreatorPage>
      <CreatorHeader
        meta="Creator Studio"
        title="Payouts"
        description="Verify once, then request payouts when your balance reaches $20."
        actions={
          <>
            <CreatorButtonLink href="/creator" variant="ghost">
              <Icon name="fa-arrow-left" /> Back to Studio
            </CreatorButtonLink>
            <CreatorButtonLink href="/creator/earnings" variant="ghost">
              <Icon name="fa-chart-line" /> Earnings
            </CreatorButtonLink>
          </>
        }
      />

      <CreatorSubnav items={CREATOR_NAV_ITEMS} />

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <CreatorMetrics
        items={[
          { label: "Available", value: usd(balance?.available_micros ?? 0) },
          { label: "Pending", value: usd(balance?.pending_micros ?? 0) },
          { label: "Paid", value: usd(balance?.paid_micros ?? 0) },
          { label: "Payout KYC", value: kyc?.status ?? "Not started" },
        ]}
      />

      <div className={styles.split}>
        <CreatorPanel title="Payout verification" meta={kyc ? kyc.status : "Not started"}>
          {kyc ? (
            <div style={{ display: "grid", gap: 12 }}>
              <CreatorStatus label={kyc.status} tone={kycTone(kyc.status)} />
              <p className={styles.rowMeta}>
                {kyc.status === "verified"
                  ? "Verified. Payouts are active."
                  : kyc.status === "pending"
                    ? "Under review. We will notify you when it is approved."
                    : kyc.reason || "Please resubmit your information."}
              </p>
            </div>
          ) : null}

          {!kycLocked ? (
            <form className={styles.form} onSubmit={onKyc} style={{ marginTop: kyc ? 20 : 0 }}>
              <CreatorField label="Legal name" htmlFor="kyc-name" error={fieldErrors.legal_name}>
                <CreatorInput id="kyc-name" value={legalName} onChange={(event) => setLegalName(event.target.value)} required />
              </CreatorField>
              <CreatorField label="Date of birth" htmlFor="kyc-dob" error={fieldErrors.date_of_birth}>
                <CreatorInput id="kyc-dob" type="date" value={dob} onChange={(event) => setDob(event.target.value)} required />
              </CreatorField>
              <CreatorField label="Country" htmlFor="kyc-country" error={fieldErrors.country_code}>
                <CreatorInput id="kyc-country" value={country} onChange={(event) => setCountry(event.target.value)} maxLength={2} required />
              </CreatorField>
              <CreatorField label="ID type" htmlFor="kyc-id-type" error={fieldErrors.id_type}>
                <CreatorSelect
                  id="kyc-id-type"
                  value={idType}
                  onValueChange={(value) => setIdType(value as typeof idType)}
                  options={[
                    { value: "national_id", label: "National ID" },
                    { value: "passport", label: "Passport" },
                    { value: "drivers_license", label: "Driver's license" },
                  ]}
                  ariaLabel="ID type"
                />
              </CreatorField>
              <CreatorField label="ID last 4 characters" htmlFor="kyc-last4" error={fieldErrors.id_last4}>
                <CreatorInput id="kyc-last4" value={idLast4} onChange={(event) => setIdLast4(event.target.value)} maxLength={4} required />
              </CreatorField>
              <CreatorField
                label="ID document"
                htmlFor="kyc-doc"
                hint="Photo or PDF of your ID. Stored privately and opened only by the review team."
                error={fieldErrors.id_document_ref}
              >
                <div className={styles.uploadRow}>
                  <label className={creatorButtonClass("secondary")} style={{ cursor: "pointer" }}>
                    <Icon name="fa-upload" />
                    {uploadingDoc === "id" ? "Uploading…" : documentRef ? "Replace ID" : "Upload ID"}
                    <input
                      id="kyc-doc"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/heic,application/pdf"
                      hidden
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void onDocument("id", file);
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                  <span className={styles.uploadName}>
                    {documentRef ? docNames.id || "Uploaded" : "No document yet"}
                  </span>
                </div>
              </CreatorField>
              <CreatorField
                label="Selfie (optional)"
                htmlFor="kyc-selfie"
                hint="A photo holding your ID speeds up the review."
                error={fieldErrors.selfie_ref}
              >
                <div className={styles.uploadRow}>
                  <label className={creatorButtonClass("secondary")} style={{ cursor: "pointer" }}>
                    <Icon name="fa-upload" />
                    {uploadingDoc === "selfie" ? "Uploading…" : selfieRef ? "Replace selfie" : "Upload selfie"}
                    <input
                      id="kyc-selfie"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/heic"
                      hidden
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void onDocument("selfie", file);
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                  <span className={styles.uploadName}>
                    {selfieRef ? docNames.selfie || "Uploaded" : "Optional"}
                  </span>
                </div>
              </CreatorField>
              <CreatorField label="Tax ID (optional)" htmlFor="kyc-tax" error={fieldErrors.tax_id}>
                <CreatorInput id="kyc-tax" value={taxId} onChange={(event) => setTaxId(event.target.value)} />
              </CreatorField>
              <div>
                <CreatorButton type="submit" disabled={saving || uploadingDoc !== null || !documentRef}>
                  <Icon name="fa-shield-halved" /> {saving ? "Submitting…" : "Submit verification"}
                </CreatorButton>
              </div>
            </form>
          ) : null}
        </CreatorPanel>

        <CreatorPanel title="Payout account" meta={account ? account.status : "Not set"}>
          {account ? (
            <div style={{ display: "grid", gap: 8, marginBottom: 20 }}>
              <CreatorStatus label={account.status} tone={account.status === "verified" ? "live" : account.status === "rejected" ? "danger" : "review"} />
              <p className={styles.rowMeta}>
                {account.method.toUpperCase()} · {account.account_name} · •••• {account.account_last4} · {account.currency}
              </p>
            </div>
          ) : null}
          <form className={styles.form} onSubmit={onAccount}>
            <CreatorField label="Method" htmlFor="account-method" error={fieldErrors.method}>
              <CreatorSelect
                id="account-method"
                value={method}
                onValueChange={(value) => setMethod(value as typeof method)}
                options={[
                  { value: "aba", label: "ABA Bank" },
                  { value: "wing", label: "Wing" },
                  { value: "khqr", label: "KHQR" },
                  { value: "bank", label: "Other bank" },
                ]}
                ariaLabel="Payout method"
              />
            </CreatorField>
            <CreatorField label="Account name" htmlFor="account-name" error={fieldErrors.account_name}>
              <CreatorInput id="account-name" value={accountName} onChange={(event) => setAccountName(event.target.value)} required />
            </CreatorField>
            <CreatorField label="Account last 4 characters" htmlFor="account-last4" error={fieldErrors.account_last4}>
              <CreatorInput id="account-last4" value={accountLast4} onChange={(event) => setAccountLast4(event.target.value)} maxLength={4} required />
            </CreatorField>
            <CreatorField label="Bank code (optional)" htmlFor="account-bank" error={fieldErrors.bank_code}>
              <CreatorInput id="account-bank" value={bankCode} onChange={(event) => setBankCode(event.target.value)} />
            </CreatorField>
            <CreatorField label="Currency" htmlFor="account-currency" error={fieldErrors.currency}>
              <CreatorSelect
                id="account-currency"
                value={currency}
                onValueChange={(value) => setCurrency(value as typeof currency)}
                options={[
                  { value: "USD", label: "USD" },
                  { value: "KHR", label: "KHR" },
                ]}
                ariaLabel="Currency"
              />
            </CreatorField>
            <div>
              <CreatorButton type="submit" variant="secondary" disabled={saving}>
                <Icon name="fa-floppy-disk" /> Save account
              </CreatorButton>
            </div>
          </form>
        </CreatorPanel>
      </div>

      <CreatorPanel title="Request a payout" className={styles.sectionGap}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div>
            <p className={styles.rowTitle}>{usd(balance?.available_micros ?? 0)} available</p>
            <p className={styles.rowMeta}>
              Minimum {usd(balance?.min_payout_micros ?? 20_000_000)} · paid monthly after verification.
            </p>
          </div>
          <CreatorButton type="button" onClick={onRequest} disabled={saving || !canRequest}>
            <Icon name="fa-money-bill-transfer" /> {saving ? "Requesting…" : "Request payout"}
          </CreatorButton>
        </div>
        {!canRequest ? (
          <p className={styles.hint} style={{ marginTop: 12 }}>
            {kyc?.status !== "verified"
              ? "Complete payout verification first."
              : account?.status !== "verified"
                ? "Your payout account needs verification."
                : "Your balance is below the $20 minimum."}
          </p>
        ) : null}
      </CreatorPanel>

      <CreatorPanel title="Payout history" className={styles.sectionGap}>
        {!data?.payouts.length ? (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>No payouts yet</p>
            <p className={styles.emptyBody}>Your first payout appears here after finance processes it.</p>
          </div>
        ) : (
          <div className={styles.list}>
            {data.payouts.map((payout) => (
              <div className={styles.row} key={payout.id}>
                <div>
                  <p className={styles.rowTitle}>{usd(payout.amount_micros)}</p>
                  <p className={styles.rowMeta}>
                    {payout.method.toUpperCase()} · requested {formatDate(payout.requested_at)}
                    {payout.paid_at ? ` · paid ${formatDate(payout.paid_at)}` : ""}
                  </p>
                </div>
                <CreatorStatus
                  label={payout.status}
                  tone={payout.status === "paid" ? "live" : payout.status === "failed" ? "danger" : "review"}
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
