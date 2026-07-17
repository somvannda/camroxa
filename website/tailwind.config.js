const preset = require('../shared/theme/tailwind-preset');

module.exports = {
  presets: [preset],
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      backgroundImage: {
        'camxora-hero':
          'radial-gradient(900px circle at 20% 10%, hsla(214,95%,62%,0.28), transparent 55%), radial-gradient(900px circle at 80% 0%, hsla(256,83%,66%,0.22), transparent 50%), linear-gradient(180deg, hsla(222,47%,5%,1), hsla(222,47%,5%,1))',
        'camxora-divider':
          'linear-gradient(90deg, transparent, hsla(214,95%,62%,0.45), hsla(256,83%,66%,0.45), transparent)',
      },
      boxShadow: {
        'glow-sm':
          '0 0 0 1px hsla(256,83%,66%,0.25), 0 8px 24px hsla(214,95%,62%,0.10)',
        'glow-md':
          '0 0 0 1px hsla(214,95%,62%,0.22), 0 16px 48px hsla(256,83%,66%,0.12)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
