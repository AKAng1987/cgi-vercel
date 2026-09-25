import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CGI — Compass Grid Identifier",
  description: "Macro regime dashboard: regime, themes, breadth, positioning.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="flex items-center gap-1 border-b border-slate-800 bg-slate-950 px-6 py-2 text-sm">
          {[
            { href: "/brief", label: "BRIEF", icon: "☀" },
            { href: "/", label: "LIVE", icon: "◉" },
            { href: "/tape", label: "TAPE", icon: "≡" },
            { href: "/backtest", label: "BACKTEST", icon: "⊞" },
            { href: "/macro", label: "MACRO", icon: "◎" },
            { href: "/markov", label: "MARKOV", icon: "⇄" },
            { href: "/cot", label: "POSITIONING", icon: "⚖" },
            { href: "/fundamentals", label: "FUNDAMENTALS", icon: "⊟" },
            { href: "/notes", label: "NOTES", icon: "✎" },
          ].map((t) => (
            <a
              key={t.href}
              href={t.href}
              className="flex items-center gap-1.5 rounded px-2 py-1 text-slate-300 transition hover:bg-slate-900 hover:text-slate-100"
            >
              <span className="text-[0.85rem] text-[#8b9dc3]">{t.icon}</span>
              {t.label}
            </a>
          ))}
        </nav>
        {children}
      </body>
    </html>
  );
}
