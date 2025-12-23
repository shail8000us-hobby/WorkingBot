const defaultTheme = require('tailwindcss/defaultTheme');

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './public/index.html',
    './src/**/*.{js,jsx,ts,tsx}'
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'var(--font-inter)', ...defaultTheme.fontFamily.sans],
        mono: ['"Roboto Mono"', ...defaultTheme.fontFamily.mono]
      },
      colors: {
        primary: {
          DEFAULT: '#0ea5e9',
          light: '#38bdf8',
          dark: '#0284c7'
        },
        success: '#22c55e',
        warning: '#f59e0b',
        danger: '#ef4444',
        surface: {
          DEFAULT: '#0f172a',
          light: '#1e293b',
          dark: '#020617'
        }
      },
      boxShadow: {
        card: '0 20px 45px -15px rgba(14, 165, 233, 0.45)',
        glow: '0 0 0 3px rgba(14, 165, 233, 0.3)'
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
};
