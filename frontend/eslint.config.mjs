import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // We intentionally read client-only values (localStorage language/theme)
      // inside useEffect and sync them to state. This is the hydration-safe
      // pattern for the App Router — doing it during render (lazy init) would
      // crash/SSR-mismatch because the server cannot read localStorage.
      // Tracked for a proper context/provider refactor; kept as a warning, not error.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
