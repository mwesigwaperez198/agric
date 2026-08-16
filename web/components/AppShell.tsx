"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore, type User } from "@/stores/auth-store";
import { apiFetch } from "@/lib/api";
import { APP_NAME } from "@/lib/utils";
import { Icons } from "@/components/icons";

const NAV_LINKS = [
  { href: "/marketplace", label: "Marketplace", icon: "store" },
  { href: "/diagnostics", label: "Diagnostics", icon: "scan" },
  { href: "/biosensor", label: "Biosensor", icon: "activity" },
  { href: "/insights", label: "Insights", icon: "trend" },
  { href: "/wallet", label: "Wallet", icon: "wallet" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { accessToken, user, setUser, logout } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (accessToken && !user) {
      apiFetch<User>("/auth/me")
        .then(setUser)
        .catch(() => {});
    }
    if (!accessToken && user) {
      // Keep the store consistent after a manual logout elsewhere.
      setUser(null);
    }
  }, [accessToken, user, setUser]);

  const isAuthPage = pathname.startsWith("/login") || pathname.startsWith("/register");
  const isHome = pathname === "/";

  return (
    <div className="min-h-dvh flex flex-col">
      {!isAuthPage && (
        <header className="sticky top-0 z-40 bg-ink-900 text-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="flex items-center gap-2">
              <Icons name="leaf" className="h-6 w-6 text-brand-400" />
              <span className="text-lg font-bold tracking-tight">{APP_NAME}</span>
              <span className="hidden rounded-full bg-brand-500/20 px-2 py-0.5 text-xs font-medium text-brand-400 sm:inline">
                by NOVARA
              </span>
            </Link>
            <nav className="hidden items-center gap-1 md:flex">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    pathname.startsWith(link.href)
                      ? "bg-white/10 text-brand-400"
                      : "text-slate-300 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  <Icons name={link.icon} className="h-4 w-4" />
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="flex items-center gap-2">
              {mounted && user ? (
                <>
                  <Link
                    href="/dashboard"
                    className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600"
                  >
                    {user.full_name.split(" ")[0]}
                  </Link>
                  <button
                    onClick={() => logout()}
                    className="rounded-lg px-2 py-1.5 text-sm text-slate-300 hover:text-white"
                    aria-label="Sign out"
                  >
                    <Icons name="logout" className="h-4 w-4" />
                  </button>
                </>
              ) : mounted ? (
                <Link
                  href="/login"
                  className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600"
                >
                  Sign in
                </Link>
              ) : (
                <div className="h-8 w-20 rounded-lg bg-white/10" />
              )}
            </div>
          </div>
        </header>
      )}

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>

      {!isAuthPage && !isHome && (
        <nav className="safe-bottom sticky bottom-0 z-40 border-t border-slate-200 bg-white md:hidden">
          <div className="grid grid-cols-5">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium ${
                  pathname.startsWith(link.href) ? "text-brand-600" : "text-slate-500"
                }`}
              >
                <Icons name={link.icon} className="h-5 w-5" />
                {link.label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </div>
  );
}
