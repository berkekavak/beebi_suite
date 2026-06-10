/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./lib/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // BeeBI brand — honey yellow (#FADB49) + dark ink, warm neutrals
        honey: {
          DEFAULT: "#FADB49",
          50: "#FFFBEA",
          100: "#FDF3C2",
          200: "#FCEB99",
          300: "#FBE271",
          400: "#FADB49",
          500: "#FADB49",
          600: "#EFC820",
          700: "#B08F00",
        },
        ink: {
          DEFAULT: "#1A1714",
          soft: "#262119",
          muted: "#6B6256",
        },
        cream: "#FAF6EF",
        sand: "#EFE7DA",
        line: "#E7DDCB",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(26,23,20,0.04), 0 8px 24px rgba(26,23,20,0.06)",
        glow: "0 8px 30px rgba(250,219,73,0.35)",
      },
      borderRadius: {
        xl2: "1rem",
      },
    },
  },
  plugins: [],
};
