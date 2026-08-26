"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/lib/sessionStore";

export function RequireAuth({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const router = useRouter();
  const { token, user, hasHydrated } = useSessionStore();

  useEffect(() => {
    if (!hasHydrated) return; // persisted session hasn't loaded yet — don't decide anything
    if (!token) {
      router.replace("/login");
      return;
    }
    if (adminOnly && user?.account_type !== "super_admin") {
      router.replace("/dashboard");
    }
  }, [hasHydrated, token, user, adminOnly, router]);

  if (!hasHydrated) return null; // avoid flashing a redirect before we actually know
  if (!token) return null;
  if (adminOnly && user?.account_type !== "super_admin") return null;

  return <>{children}</>;
}
