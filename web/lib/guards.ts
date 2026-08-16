"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export function useRequireAuth(): void {
  const router = useRouter();
  const token = useAuthStore((s) => s.accessToken);
  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);
}

export function useRequireRole(roles: string[]): void {
  const router = useRouter();
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    if (user && !roles.includes(user.role)) {
      router.replace("/dashboard");
    }
  }, [token, user, roles, router]);
}
