"use client";

import { useEffect, useState } from "react";

type AuthMode = "in" | "out";

export function AuthPreview() {
  const [mode, setMode] = useState<AuthMode>("in");

  useEffect(() => {
    document.body.dataset.auth = mode;
  }, [mode]);

  if (process.env.NODE_ENV === "production") return null;

  return (
    <button
      className="btn btn-ghost dev-auth-preview"
      type="button"
      onClick={() => setMode((value) => (value === "in" ? "out" : "in"))}
      style={{ height: 34, padding: "0 10px", fontSize: 11 }}
      title="Development-only auth preview"
    >
      {mode === "in" ? "Preview guest" : "Preview signed in"}
    </button>
  );
}
