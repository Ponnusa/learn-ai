"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/lib/sessionStore";

export function RequireAuth({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const router = useRouter();
  const { token, user } = useSessionStore();

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    if (adminOnly && user?.account_type !== "super_admin") {
      router.replace("/dashboard");
    }
  }, [token, user, adminOnly, router]);

  if (!token) return null;
  if (adminOnly && user?.account_type !== "super_admin") return null;

  return <>{children}</>;
}
