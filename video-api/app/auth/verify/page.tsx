"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { verifyMagicLink, ApiError } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

function VerifyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const setSession = useSessionStore((s) => s.setSession);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("Missing sign-in token.");
      return;
    }
    verifyMagicLink(token)
      .then((res) => {
        setSession(res.token, res.user);
        router.replace("/dashboard");
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "This link is invalid or expired.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="max-w-sm mx-auto px-6 py-24 text-center">
      {error ? (
        <>
          <p className="mb-2" style={{ color: "var(--revoked)" }}>
            {error}
          </p>
          <a href="/login" className="text-sm underline" style={{ color: "var(--accent-ink)" }}>
            Request a new link
          </a>
        </>
      ) : (
        <p style={{ color: "var(--text-soft)" }}>Signing you in…</p>
      )}
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<div className="max-w-sm mx-auto px-6 py-24 text-center">Loading…</div>}>
      <VerifyInner />
    </Suspense>
  );
}
