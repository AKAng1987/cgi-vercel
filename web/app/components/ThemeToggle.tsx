"use client";

import { useEffect, useState } from "react";

const KEY = "cgi-theme";
type Mode = "system" | "light" | "dark";

const NEXT: Record<Mode, Mode> = { system: "light", light: "dark", dark: "system" };
const ICON: Record<Mode, string> = { system: "◐", light: "☀", dark: "☾" };
const LABEL: Record<Mode, string> = {
  system: "Following your computer",
  light: "Light",
  dark: "Dark",
};

/**
 * Three-way theme control: follow the computer, force light, force dark.
 *
 * "system" is the DEFAULT and the absence of a stored value, so a first-time
 * visitor gets whatever their machine is set to rather than an opinion of
 * ours.
 *
 * The resolution of system -> light|dark happens in the inline script in
 * layout.tsx, not here, so `data-theme` is always a concrete value by the time
 * anything paints. That keeps the CSS to a single [data-theme="light"] block
 * instead of duplicating the whole palette inside a prefers-color-scheme
 * media query, where the two copies would eventually drift apart.
 *
 * Every localStorage access is wrapped: it throws outright in a private window
 * and an unhandled throw in the nav would take down every page.
 */
function read(): Mode {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* private window or site data blocked */
  }
  return "system";
}

function apply(mode: Mode) {
  const resolved =
    mode === "system"
      ? window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark"
      : mode;
  document.documentElement.setAttribute("data-theme", resolved);
}

export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>("system");

  useEffect(() => {
    setMode(read());
  }, []);

  // While following the computer, track it live -- someone on a schedule that
  // flips at sunset should see the page flip too, without a reload.
  useEffect(() => {
    if (mode !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [mode]);

  function cycle() {
    const next = NEXT[mode];
    setMode(next);
    apply(next);
    try {
      if (next === "system") window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, next);
    } catch {
      /* not remembered, but still applied for this session */
    }
  }

  return (
    <button
      onClick={cycle}
      aria-label={`Theme: ${LABEL[mode]}. Click for ${LABEL[NEXT[mode]]}.`}
      title={`Theme: ${LABEL[mode]} — click for ${LABEL[NEXT[mode]]}`}
      className="rounded px-1.5 py-1 text-[0.8rem] text-slate-400 transition hover:bg-slate-900 hover:text-slate-100"
    >
      {ICON[mode]}
    </button>
  );
}
