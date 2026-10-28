"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchRedeemHistory,
  redeemCode,
  type RedeemHistoryItem,
  type RedeemResult,
} from "@/lib/redeem-api";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
}

export function RedeemView() {
  const { user, loading: authLoading, refresh } = useAuth();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RedeemResult | null>(null);
  const [history, setHistory] = useState<RedeemHistoryItem[]>([]);

  useEffect(() => {
    if (!user) {
      setHistory([]);
      return;
    }
    let active = true;
    fetchRedeemHistory()
      .then((items) => {
        if (active) setHistory(items);
      })
      .catch(() => {
        if (active) setHistory([]);
      });
    return () => {
      active = false;
    };
  }, [user]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = code.trim().toUpperCase();
    if (!value) {
      setError("Enter a redeem code.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const redeemed = await redeemCode(value);
      setResult(redeemed);
      setCode("");
      await refresh();
      const items = await fetchRedeemHistory();
      setHistory(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not redeem this code");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading…</p>;
  }

  if (!user) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-gift" /></span>
          <h1>Redeem a code</h1>
          <p>Sign in to redeem a credit code and add credits to your account.</p>
          <Link className="btn btn-primary" href="/login?next=/redeem">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Rewards</div>
          <h1>Redeem a code.</h1>
          <p>Enter a Camxora credit code. Credits are added to your balance instantly.</p>
        </div>
        <span className="invite-hero-icon"><Icon name="fa-gift" /></span>
      </div>

      <div className="redeem-grid">
        <section className="panel redeem-panel">
          <h2>Enter your code</h2>
          <p>Codes are case-insensitive. Each code can only be redeemed once.</p>
          <form onSubmit={onSubmit} className="redeem-form">
            <label htmlFor="redeem-code">Redeem code</label>
            <div className="redeem-row">
              <input
                id="redeem-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="CAMXORA-XXXX"
                autoComplete="off"
                spellCheck={false}
                required
              />
              <button className="btn btn-primary" type="submit" disabled={busy}>
                <Icon name="fa-check" /> {busy ? "Redeeming…" : "Redeem"}
              </button>
            </div>
          </form>

          {error ? (
            <p className="fine redeem-error" role="alert">{error}</p>
          ) : null}

          {result ? (
            <div className="redeem-success" role="status">
              <span className="redeem-success-icon"><Icon name="fa-check" /></span>
              <div>
                <strong>Code redeemed</strong>
                <p>
                  {result.credit_amount
                    ? `+${result.credit_amount.toLocaleString()} credits added.`
                    : result.message || "Your reward has been added."}
                  {result.new_balance != null
                    ? ` New balance: ${result.new_balance.toLocaleString()} credits.`
                    : ""}
                </p>
              </div>
            </div>
          ) : null}
        </section>

        <section className="panel invite-panel">
          <h2><Icon name="fa-gift" /> Where codes come from</h2>
          <ol className="invite-steps">
            <li><span>1</span> Weekly community challenges.</li>
            <li><span>2</span> Camxora campaigns and partner drops.</li>
            <li><span>3</span> Support credits after an issue.</li>
          </ol>
          <p className="invite-note">
            Codes are single-use unless stated otherwise. Discount codes are applied
            at checkout, not here.
          </p>
        </section>
      </div>

      <section className="panel invite-friends">
        <div className="sec-head">
          <h2><Icon name="fa-clock-rotate-left" /> Recent redemptions</h2>
        </div>
        {!history.length ? (
          <div className="invite-empty">No codes redeemed yet.</div>
        ) : (
          <div className="invite-table-wrap">
            <table className="invite-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Reward</th>
                  <th className="right">Credits</th>
                  <th>Status</th>
                  <th>Redeemed</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}>
                    <td className="redeem-code-cell">{item.code}</td>
                    <td>{item.description || item.reward_type}</td>
                    <td className="right">{item.credit_amount?.toLocaleString() || "—"}</td>
                    <td><span className="invite-status rewarded">{item.status}</span></td>
                    <td>{formatDate(item.created_at)}</td>
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
