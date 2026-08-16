"use client";

import { useEffect } from "react";
import { registerSync } from "@/lib/offline-queue";

export function PwaInit() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {});
    registerSync();
  }, []);
  return null;
}
