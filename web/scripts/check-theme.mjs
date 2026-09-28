/**
 * Fail if a Tailwind colour is used in the app but has no light-mode value.
 *
 * Light mode works by remapping Tailwind's colour variables under
 * [data-theme="light"]. The slate ramp is remapped wholesale, but every
 * accent is a hand-written line in globals.css -- and a hand-written list
 * drifts. On 2026-09-28, 24 colours were in use with no light value at all,
 * so they rendered at their dark-tuned value on a white page. text-amber-400
 * measured 1.65:1 against the background.
 *
 * That is the same failure mode as the 38 backtest tickers and the stale
 * FOMC calendar: a list in one place, the work in another, and nothing
 * checking that they agree. This is the check.
 *
 * It also rejects arbitrary hex in class names -- bg-[#1F2937]. Those
 * compile to a fixed colour and CANNOT be remapped by any theme, so they
 * stayed dark navy on a white page. The first version of this script only
 * looked at family-shade utilities and missed all 36 of them, which is why
 * TAPE and BACKTEST were still broken after light mode was "fixed". Use a
 * CSS variable instead: bg-[var(--cgi-surface)].
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["app", "lib"];
const CSS = "app/globals.css";

// Remapped as a whole ramp, so individual shades need no separate entry.
const RAMP_HANDLED = new Set(["slate"]);

const UTILITY =
  /\b(?:text|bg|border|decoration|ring|fill|stroke|from|to|via|divide|outline|shadow|accent|caret)-([a-z]+)-(\d{2,3})\b/g;

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(p)) out.push(p);
  }
  return out;
}

const css = readFileSync(CSS, "utf8");
const lightBlock = css.slice(css.indexOf('[data-theme="light"]'));
const defined = new Set(
  [...lightBlock.matchAll(/--color-([a-z]+)-(\d{2,3})\s*:/g)].map((m) => `${m[1]}-${m[2]}`),
);

const used = new Map();
for (const root of ROOTS) {
  for (const file of walk(root)) {
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(UTILITY)) {
      const [, family, shade] = m;
      if (RAMP_HANDLED.has(family)) continue;
      const key = `${family}-${shade}`;
      if (!used.has(key)) used.set(key, new Set());
      used.get(key).add(file);
    }
  }
}

// Arbitrary hex in a class name can never be themed.
const HEX = /\b(?:text|bg|border|ring|fill|stroke|from|to|via|decoration|shadow|accent|outline)-\[#[0-9a-fA-F]{3,8}\]/g;
const literals = new Map();
for (const root of ROOTS) {
  for (const file of walk(root)) {
    for (const m of readFileSync(file, "utf8").matchAll(HEX)) {
      if (!literals.has(m[0])) literals.set(m[0], new Set());
      literals.get(m[0]).add(file);
    }
  }
}
if (literals.size) {
  console.error(
    `\n${literals.size} hard-coded colour(s) in class names. These compile to a\n` +
      `fixed hex and cannot be remapped, so they keep their dark value on white.\n`,
  );
  for (const [k, files] of literals) {
    console.error(`  ${k.padEnd(26)} ${[...files].slice(0, 2).join(", ")}`);
  }
  console.error(`\nUse a themed variable instead, e.g. bg-[var(--cgi-surface)].\n`);
  process.exit(1);
}

const missing = [...used.keys()].filter((k) => !defined.has(k)).sort();

if (missing.length) {
  console.error(
    `\n${missing.length} colour(s) used with no light-mode value in ${CSS}.\n` +
      `On a white page these render at their dark-tuned value.\n`,
  );
  for (const k of missing) {
    const files = [...used.get(k)].slice(0, 3).join(", ");
    console.error(`  ${k.padEnd(16)} ${files}`);
  }
  console.error(
    `\nAdd each to the [data-theme="light"] block. The rule is by ROLE:\n` +
      `  a light shade used as TEXT darkens;\n` +
      `  a deep shade used as a BORDER or BACKGROUND lightens.\n`,
  );
  process.exit(1);
}

console.log(
  `theme ok: ${used.size} accent colours in use, all have a light value; ` +
    `no hard-coded hex in class names`,
);
