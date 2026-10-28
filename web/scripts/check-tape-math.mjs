/**
 * Checks lib/tapeMath.ts (the TAPE views' arithmetic) against hand-computed rows: relative strength, stretch z,
 * ladder state, quadrants, means, staleness, tile strength. Run: node scripts/check-tape-math.mjs
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const out = mkdtempSync(join(tmpdir(), "tapemath-"));
try {
  execFileSync("npx", ["tsc", "lib/tapeMath.ts", "--outDir", out, "--module", "commonjs", "--target", "es2020", "--skipLibCheck", "--moduleResolution", "node"], { stdio: "ignore" });
} catch {
  /* tsc exits non-zero because the type-only "@/lib/types" import does not resolve outside the project; the JS is still written */
}
execFileSync("node", ["scripts/tape-math-cases.cjs", join(out, "tapeMath.js")], { stdio: "inherit" });
