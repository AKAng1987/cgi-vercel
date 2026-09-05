import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CGI Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="border-b border-slate-800 bg-slate-950 px-6 py-2 text-sm">
          <a href="/" className="mr-4 text-slate-300 hover:text-slate-100">
            LIVE
          </a>
          <a href="/macro" className="text-slate-300 hover:text-slate-100">
            MACRO
          </a>
        </nav>
        {children}
      </body>
    </html>
  );
}
