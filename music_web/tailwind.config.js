import type { Config } from 'tailwindcss';
import preset from '../shared/theme/tailwind-preset.js';

export default {
  presets: [preset],
  content: ['./src/**/*.{ts,tsx}'],
} satisfies Config;
