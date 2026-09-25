"use client";

import { useEffect, useState } from "react";

const KEY = "cgi-theme";

/**
 * Light/dark toggle.
 *
 * localStorage is wrapped in try/catch on BOTH read and write: it throws
 * outright in a private window and in browsers with site data blocked, and an
 * unhandled throw here would take down the whole nav on every page. A failed
 * read simply means the toggle does not persist, which is a far smaller
 * problem than a blank site.
 *
 * The initial value is read from the DOM, not from storage, because the inline
 * script in layout.tsx has already applied the stored theme before paint.
 * Reading storage again here would re-derive the same answer one render later
 * and cause a flash.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const cur = document.documentElement.getAttribute("data-theme");
    setTheme(cur === "light" ? "light" : "dark");
  }, []);

  function flip() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      window.localStorage.setItem(KEY, next);
    } catch {
      /* private window or site data blocked -- the toggle still works for
         this session, it just will not be remembered */
    }
  }

  return (
    <button
      onClick={flip}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="rounded px-1.5 py-1 text-[0.8rem] text-slate-400 transition hover:bg-slate-900 hover:text-slate-100"
    >
      {theme === "dark" ? "☾" : "☀"}
    </button>
  );
}
