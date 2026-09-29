import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface-1)",
        "surface-2": "var(--surface-2)",
        sunken: "var(--surface-sunken)",
        plane: "var(--plane)",
        ink: "var(--text-primary)",
        "ink-2": "var(--text-secondary)",
        muted: "var(--text-muted)",
        hairline: "var(--border)",
        grid: "var(--gridline)",
        brand: "var(--brand)",
        "brand-2": "var(--brand-2)",
      },
      boxShadow: {
        e1: "var(--elev-1)",
        e2: "var(--elev-2)",
        e3: "var(--elev-3)",
        brand: "var(--glow-brand)",
      },
      borderRadius: {
        xl: "var(--radius)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
