import preset from '../shared/theme/tailwind-preset.js';

/** @type {import('tailwindcss').Config} */
export default {
  presets: [preset],
  content: ['./src/**/*.{ts,tsx}'],
  plugins: [require('tailwindcss-animate')],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        xl: '7px',
        '2xl': '7px',
        '3xl': '7px',
      },
    },
  },
};
