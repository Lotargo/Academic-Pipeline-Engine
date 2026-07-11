import { defineConfig, globalIgnores } from "eslint/config"
import nextTs from "eslint-config-next/typescript"
import nextVitals from "eslint-config-next/core-web-vitals"

export default defineConfig([
  ...nextVitals.map((config, index) => index === 0 ? {
    ...config,
    rules: {
      ...config.rules,
      "react/no-unescaped-entities": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/set-state-in-effect": "warn",
    },
  } : config),
  ...nextTs.map((config, index) => index === 2 ? {
    ...config,
    rules: {
      ...config.rules,
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/no-unused-expressions": "warn",
    },
  } : config),
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
])
