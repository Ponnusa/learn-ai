"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSessionStore } from "@/lib/sessionStore";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/generate", label: "Generate" },
  { href: "/videos", label: "Videos" },
  { href: "/docs", label: "Docs" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clearSession } = useSessionStore();

  function signOut() {
    clearSession();
    router.push("/login");
  }

  return (
    <header
      className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b"
      style={{ background: "var(--bg)", borderColor: "var(--border)" }}
    >
      <div className="flex items-center gap-8">
        <Link href="/" className="font-semibold tracking-tight flex items-center gap-2">
          <span style={{ color: "var(--accent)" }}>●</span> LearnX Video API
        </Link>
        {user && (
          <nav className="flex items-center gap-1">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="px-3 py-1.5 rounded-md text-sm transition-colors"
                style={{
                  color: pathname === l.href ? "var(--text)" : "var(--text-soft)",
                  background: pathname === l.href ? "var(--surface-soft)" : "transparent",
                }}
              >
                {l.label}
              </Link>
            ))}
            {user.account_type === "super_admin" && (
              <Link
                href="/admin"
                className="px-3 py-1.5 rounded-md text-sm transition-colors"
                style={{
                  color: pathname === "/admin" ? "var(--text)" : "var(--text-soft)",
                  background: pathname === "/admin" ? "var(--surface-soft)" : "transparent",
                }}
              >
                Admin
              </Link>
            )}
          </nav>
        )}
      </div>
      {user ? (
        <div className="flex items-center gap-3 text-sm">
          <span style={{ color: "var(--text-faint)" }}>{user.email}</span>
          <button
            onClick={signOut}
            className="px-3 py-1.5 rounded-md border text-sm"
            style={{ borderColor: "var(--border)", color: "var(--text-soft)" }}
          >
            Sign out
          </button>
        </div>
      ) : (
        <Link
          href="/login"
          className="px-3 py-1.5 rounded-md text-sm font-medium"
          style={{ background: "var(--accent)", color: "#04201C" }}
        >
          Sign in
        </Link>
      )}
    </header>
  );
}
