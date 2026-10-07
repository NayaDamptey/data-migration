import type { Config } from "tailwindcss";

// One colour: white plus shades of blue. Navy for text, a strong blue for actions,
// deep blue for the frame, pale blues for fills and lines. Status uses blue shades
// together with its label (strong = done, mid = needs review, deep navy = failed).
// The only other colours are the systems' own logos.
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FFFFFF",
        surface: "#FFFFFF",
        sunken: "#EEF3FF",
        ink: "#0B1F4D",
        muted: "#4A5F8C",
        faint: "#93A3C4",
        line: "#DCE5F7",
        accent: { DEFAULT: "#0A1F44", soft: "#E6EEFF", ink: "#05122B" },
        ok: { DEFAULT: "#0A1F44", soft: "#E6EEFF" },
        warn: { DEFAULT: "#5577C2", soft: "#F0F4FD" },
        bad: { DEFAULT: "#0B1F4D", soft: "#D6E1FA" },
        nav: { DEFAULT: "#061633", hover: "#0F2552", line: "#16305F", text: "#A9B8D9" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Cascadia Mono", "Consolas", "Menlo", "monospace"],
      },
      // Square boxes everywhere; only pills, badges and avatars (rounded-full) stay round
      borderRadius: { sm: "0", DEFAULT: "0", md: "0", lg: "0", xl: "0", "2xl": "0", "3xl": "0" },
      boxShadow: {
        card: "0 1px 2px rgba(10,31,68,0.06), 0 4px 12px rgba(10,31,68,0.06)",
        pop: "0 8px 32px rgba(0,0,0,0.16)",
      },
    },
  },
  plugins: [],
} satisfies Config;
