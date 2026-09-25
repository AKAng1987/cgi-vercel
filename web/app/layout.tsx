import type { Metadata } from "next";
import "./globals.css";
import { ThemeToggle } from "./components/ThemeToggle";

/**
 * Applied before first paint, so a light-mode user never sees a dark flash.
 * Must stay inline and synchronous -- a React effect runs after paint, which
 * is exactly one frame too late. Wrapped in try/catch because localStorage
 * throws in a private window.
 */
const NO_FLASH = `try{var t=localStorage.getItem('cgi-theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}`;

export const metadata: Metadata = {
  title: "CGI — Compass Grid Identifier",
  description: "Macro regime dashboard: regime, themes, breadth, positioning.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH }} />
      </head>
      <body>
        <nav className="flex flex-wrap items-center gap-1 border-b border-slate-800 bg-slate-950 px-6 py-2 text-sm">
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
              <span className="text-[0.85rem] text-[color:var(--cgi-accent)]">{t.icon}</span>
              {t.label}
            </a>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[0.68rem] tabular-nums text-slate-500">{today}</span>
            <ThemeToggle />
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
