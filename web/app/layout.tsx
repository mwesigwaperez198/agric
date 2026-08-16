import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { PwaInit } from "@/components/PwaInit";
import { APP_NAME } from "@/lib/utils";

export const metadata: Metadata = {
  title: `${APP_NAME} — Farmer-Consumer Marketplace`,
  description:
    "Direct farm-to-fork marketplace connecting coffee and agri-food producers with consumers. Biosensor tracking, vision diagnostics, and localized AI support.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: APP_NAME },
  applicationName: APP_NAME,
  icons: {
    icon: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
    apple: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="manifest" href="/manifest.webmanifest" />
      </head>
      <body>
        <AppShell>{children}</AppShell>
        <PwaInit />
      </body>
    </html>
  );
}
