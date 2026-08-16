import Link from "next/link";
import { Icons } from "@/components/icons";

const FEATURES = [
  {
    icon: "store",
    title: "Direct Marketplace",
    desc: "Buy coffee, maize, vanilla and more straight from farmers. No middlemen, fair prices.",
    href: "/marketplace",
  },
  {
    icon: "shield",
    title: "Escrow & Commissions",
    desc: "Funds held securely until delivery, with a transparent 2.5% platform commission.",
    href: "/wallet",
  },
  {
    icon: "scan",
    title: "Vision Diagnostics",
    desc: "Snap a leaf or animal photo to detect rust, blight or infestation in seconds.",
    href: "/diagnostics",
  },
  {
    icon: "activity",
    title: "Biosensor Tracking",
    desc: "Live mycotoxin, pesticide and moisture monitoring for safe, export-ready produce.",
    href: "/biosensor",
  },
  {
    icon: "mic",
    title: "Localized Voice AI",
    desc: "Ask questions in Luganda, Swahili, Acholi or Runyankore and hear answers spoken back.",
    href: "/diagnostics",
  },
  {
    icon: "trend",
    title: "Market Insights",
    desc: "Price forecasts and weather-driven crop recommendations to guide planting decisions.",
    href: "/insights",
  },
];

export default function HomePage() {
  return (
    <div className="animate-fade-in">
      <section className="overflow-hidden rounded-3xl bg-gradient-to-br from-ink-900 via-ink-900 to-emerald-950 text-white">
        <div className="grid gap-8 p-8 md:grid-cols-2 md:p-12">
          <div className="flex flex-col justify-center gap-4">
            <span className="inline-flex w-fit items-center gap-2 rounded-full bg-brand-500/20 px-3 py-1 text-xs font-semibold text-brand-400">
              <Icons name="leaf" className="h-3.5 w-3.5" /> Shaping a New Era of Tech in Uganda
            </span>
            <h1 className="text-3xl font-bold leading-tight md:text-5xl">
              From the farmer&apos;s field, <span className="text-brand-400">straight to your table.</span>
            </h1>
            <p className="max-w-md text-slate-300">
              A farm-to-fork marketplace that connects agricultural producers directly with consumers —
              with biosensor safety tracking, AI diagnostics and localized voice support.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link
                href="/marketplace"
                className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-600"
              >
                Browse marketplace <Icons name="arrow" className="h-4 w-4" />
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-2 rounded-xl border border-white/20 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10"
              >
                Become a seller
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:gap-4">
            {FEATURES.slice(0, 4).map((f) => (
              <Link
                key={f.title}
                href={f.href}
                className="group rounded-2xl border border-white/10 bg-white/5 p-4 transition-colors hover:bg-white/10"
              >
                <Icons name={f.icon} className="h-6 w-6 text-brand-400" />
                <h3 className="mt-3 text-sm font-semibold">{f.title}</h3>
                <p className="mt-1 text-xs text-slate-400">{f.desc}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        {[
          { icon: "shield", title: "Secure transactions", desc: "AES-256 encryption, 2FA and SHA-256 ledger hashing." },
          { icon: "truck", title: "Verified delivery", desc: "Funds held in escrow until delivery is confirmed." },
          { icon: "globe", title: "Rural-ready offline", desc: "PWA caching and background sync for weak networks." },
        ].map((b) => (
          <div key={b.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <Icons name={b.icon} className="h-6 w-6 text-brand-600" />
            <h3 className="mt-3 font-semibold text-slate-900">{b.title}</h3>
            <p className="mt-1 text-sm text-slate-500">{b.desc}</p>
          </div>
        ))}
      </section>

      <section className="mt-8">
        <div className="grid gap-4 sm:grid-cols-2">
          {FEATURES.slice(4).map((f) => (
            <Link
              key={f.title}
              href={f.href}
              className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-brand-400"
            >
              <div className="rounded-xl bg-brand-50 p-2.5 text-brand-600">
                <Icons name={f.icon} className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">{f.title}</h3>
                <p className="mt-1 text-sm text-slate-500">{f.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
