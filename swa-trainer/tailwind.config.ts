import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './data/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        swa: {
          navy: '#0f2044',
          blue: '#1e3a8a',
          gold: '#f59e0b',
          'gold-light': '#fcd34d',
          'blue-light': '#dbeafe',
        },
      },
    },
  },
  plugins: [],
};
export default config;
