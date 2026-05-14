import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: {
        sm: "640px",
        md: "768px",
        lg: "1024px",
        xl: "1200px",
      },
    },
    extend: {
      colors: {
        bg: {
          base: "#FFFFFF",
          soft: "#F4F4F4",
          gray: "#EEEEEE",
        },
        line: {
          DEFAULT: "#ECECEC",
          strong: "#D0D0D0",
        },
        ink: {
          primary: "#1F1F1F",
          secondary: "#666666",
          muted: "#ADADAD",
          faint: "#D0D0D0",
        },
        brand: {
          DEFAULT: "#26AD50",
          hover: "#1F9544",
          dark: "#144942",
          soft: "#E5F4EA",
        },
        link: "#1F6FBF",
        severity: {
          critical: { DEFAULT: "#C73C3C", soft: "#FBE9E9", border: "#F2BCBC" },
          high: { DEFAULT: "#D87A1A", soft: "#FBEDD9", border: "#EFCB94" },
          medium: { DEFAULT: "#C99A1F", soft: "#FAF1D2", border: "#EDD584" },
          low: { DEFAULT: "#3E7FBF", soft: "#E6F0FA", border: "#B5D0EB" },
          inconclusive: { DEFAULT: "#666666", soft: "#F4F4F4", border: "#D0D0D0" },
        },
      },
      fontFamily: {
        sans: ["var(--font-onest)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        eyebrow: ["0.6875rem", { letterSpacing: "0.14em", lineHeight: "1" }],
      },
      letterSpacing: {
        eyebrow: "0.14em",
      },
      borderRadius: {
        card: "1rem",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.4)", opacity: "0.6" },
        },
        "flash-in": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "20%, 80%": { opacity: "1", transform: "translateY(0)" },
          "100%": { opacity: "0", transform: "translateY(-4px)" },
        },
        "count-bump": {
          "0%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.15)" },
          "100%": { transform: "scale(1)" },
        },
        "progress-stripe": {
          from: { backgroundPosition: "0 0" },
          to: { backgroundPosition: "20px 0" },
        },
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
        "flash-in": "flash-in 2.6s ease-out forwards",
        "count-bump": "count-bump 320ms ease-out",
        "progress-stripe": "progress-stripe 1s linear infinite",
        marquee: "marquee 45s linear infinite",
        rise: "rise 360ms ease-out forwards",
      },
    },
  },
  plugins: [animate],
};

export default config;
