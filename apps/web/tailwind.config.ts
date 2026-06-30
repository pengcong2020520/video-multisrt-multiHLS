import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17202a',
        line: '#d6dde6',
        panel: '#f6f8fb',
        accent: '#0f766e',
        warn: '#b45309',
        danger: '#b91c1c',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(17, 24, 39, 0.06)',
      },
    },
  },
  plugins: [],
} satisfies Config
