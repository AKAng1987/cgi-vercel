"use client";

import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

/**
 * Current theme, kept in sync with the `data-theme` attribute the toggle sets
 * on <html>.
 *
 * A MutationObserver is used rather than a React context or a custom event:
 * the attribute IS the source of truth (an inline script sets it before first
 * paint, before React exists), so observing it directly means there is nothing
 * to keep in sync and no way for the two to disagree. Any future code that
 * flips the attribute gets picked up for free.
 *
 * Starts as "dark" to match the server render, then corrects in the effect --
 * reading the DOM during render would break hydration.
 */
export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const el = document.documentElement;
    const read = () => setTheme(el.getAttribute("data-theme") === "light" ? "light" : "dark");
    read();
    const obs = new MutationObserver(read);
    obs.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);

  return theme;
}
