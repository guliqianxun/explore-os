import type { Config } from "tailwindcss";

// ft-026: extend with editorial tokens (defined in src/styles/tokens.css).
// Keep shadcn/ui HSL vars intact for existing components.
const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      fontFamily: {
        serif: ["var(--font-serif)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      colors: {
        // shadcn/ui (kept)
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // ft-026 editorial palette (raw vars; opt-in)
        editorial: {
          bg: "var(--bg)",
          "bg-soft": "var(--bg-soft)",
          "bg-muted": "var(--bg-muted)",
          fg: "var(--fg)",
          "fg-soft": "var(--fg-soft)",
          "fg-muted": "var(--fg-muted)",
          rule: "var(--rule)",
          accent: "var(--accent)",
          "accent-soft": "var(--accent-soft)",
        },
        claim: {
          proposal: "var(--proposal)",
          "proposal-soft": "var(--proposal-soft)",
          result: "var(--result)",
          "result-soft": "var(--result-soft)",
          ablation: "var(--ablation)",
          "ablation-soft": "var(--ablation-soft)",
          theoretical: "var(--theoretical)",
          "theoretical-soft": "var(--theoretical-soft)",
        },
        counter: {
          bg: "var(--counter-bg)",
          fg: "var(--counter-fg)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        card: "var(--radius-card)",
      },
      maxWidth: {
        reading: "var(--reading-max-w)",
        drawer: "var(--drawer-w)",
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        lift: "var(--shadow-lift)",
      },
    },
  },
  plugins: [],
};

export default config;
