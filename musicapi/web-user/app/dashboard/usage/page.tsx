"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface Usage {
  total_24h: number;
  success_24h: number;
  failed_24h: number;
  total_spend: number;
  series: { day: string; count: number }[];
}

interface EndpointCount {
  endpoint: string;
  count: number;
}

export default function UsagePage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [byEndpoint, setByEndpoint] = useState<EndpointCount[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<Usage>("/me/usage"), apiFetch<EndpointCount[]>("/me/usage/by-endpoint")])
      .then(([u, e]) => {
        setUsage(u);
        setByEndpoint(e);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  const maxCount = usage ? Math.max(1, ...usage.series.map((s) => s.count)) : 1;
  const total30 = byEndpoint.reduce((s, e) => s + e.count, 0);
  const successRate = usage && usage.total_24h > 0 ? Math.round((usage.success_24h / usage.total_24h) * 100) : 100;

  const stats = [
    { label: "Requests (24h)", value: usage?.total_24h ?? 0 },
    { label: "Success (24h)", value: usage?.success_24h ?? 0 },
    { label: "Failed (24h)", value: usage?.failed_24h ?? 0 },
    { label: "Success rate", value: `${successRate}%` },
    { label: "Total spend", value: `$${(usage?.total_spend ?? 0).toFixed(2)}` },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">API Usages</h1>
      <p className="mt-1 text-sm text-white/50">Detailed usage and success metrics.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
        {stats.map((s) => (
          <div key={s.label} className="glass rounded-2xl p-5">
            <div className="text-sm text-white/50">{s.label}</div>
            <div className="grad-text mt-1 text-3xl font-extrabold">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-3 text-sm font-semibold text-white/50">Requests — last 30 days</div>
        <div className="flex h-40 items-end gap-1">
          {(usage?.series ?? []).map((s) => (
            <div key={s.day} className="group relative flex-1" title={`${s.day}: ${s.count}`}>
              <div className="grad-bg w-full rounded-t" style={{ height: `${Math.max(4, (s.count / maxCount) * 100)}%` }} />
            </div>
          ))}
          {(!usage || usage.series.length === 0) && <div className="text-sm text-white/50">No usage yet.</div>}
        </div>
      </div>

      <div className="glass mt-6 overflow-x-auto rounded-2xl p-2">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-white/50">
              <th className="px-3 py-2">Endpoint</th>
              <th className="px-3 py-2">Requests (30d)</th>
              <th className="px-3 py-2">Share</th>
            </tr>
          </thead>
          <tbody>
            {byEndpoint.map((e) => (
              <tr key={e.endpoint} className="border-t border-white/5">
                <td className="px-3 py-2 font-medium text-white">{e.endpoint}</td>
                <td className="px-3 py-2 text-white">{e.count}</td>
                <td className="px-3 py-2 text-white/50">{total30 ? Math.round((e.count / total30) * 100) : 0}%</td>
              </tr>
            ))}
            {byEndpoint.length === 0 && (
              <tr>
                <td colSpan={3} className="px-3 py-6 text-center text-white/50">No requests yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
