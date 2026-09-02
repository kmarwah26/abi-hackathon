/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1B3139",
          900: "#0B1F26",
          800: "#122b33",
          700: "#1B3139",
          600: "#2A4A55",
        },
        brand: {
          red: "#FF3621",
          redDark: "#D62D18",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          muted: "#F7FAFB",
          sunken: "#EEF3F5",
        },
        line: "#E3E9ED",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,34,40,0.04), 0 4px 16px rgba(16,34,40,0.06)",
        pop: "0 8px 30px rgba(16,34,40,0.12)",
      },
      borderRadius: {
        xl: "14px",
        "2xl": "18px",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.18s ease-out",
      },
    },
  },
  plugins: [],
};
