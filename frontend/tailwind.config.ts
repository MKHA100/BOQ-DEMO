import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./features/**/*.{js,ts,jsx,tsx,mdx}",
    "./shared/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        surface: "#f5f7fb",
        panel: "#ffffff",
        border: "#d9dee8",
        ink: "#172033",
        muted: "#657085",
        primary: "#1d4ed8"
      }
    }
  },
  plugins: []
};

export default config;
