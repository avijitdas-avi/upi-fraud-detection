/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Base console surfaces — dark charcoal-navy, not pure black
        base: "#0F1419",
        panel: "#161D26",
        border: "#26313D",
        borderStrong: "#37444F",
        // Text
        textPrimary: "#E6EDF3",
        textSecondary: "#8B98A5",
        textMuted: "#5C6B78",
        // The one interactive accent — separate from risk semantics
        accent: "#3ECFCB",
        // Risk tier colors — the actual semantic system (Section 6 of the spec)
        riskLow: "#3DDC84",
        riskMedium: "#F2C94C",
        riskHigh: "#FF9B4A",
        riskCritical: "#FF5C5C",
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
