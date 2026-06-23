import type { Config } from "tailwindcss";

// WeBook-inspired dark theme with a magenta → purple brand gradient.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0b0f",
        surface: "#14141c",
        surface2: "#1c1c2a",
        line: "#2a2a3d",
        muted: "#8888aa",
        brand: {
          pink: "#e6007e",
          mid: "#b818c8",
          purple: "#7b2ff7",
        },
      },
      backgroundImage: {
        brand: "linear-gradient(135deg, #e6007e 0%, #7b2ff7 100%)",
        "brand-soft":
          "radial-gradient(60% 60% at 50% 0%, rgba(123,47,247,0.25), rgba(11,11,15,0) 70%)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      keyframes: {
        floaty: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        pulseDot: { "0%, 100%": { opacity: "0.4" }, "50%": { opacity: "1" } },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        floaty: "floaty 6s ease-in-out infinite",
        pulseDot: "pulseDot 1.6s ease-in-out infinite",
        slideUp: "slideUp .25s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
