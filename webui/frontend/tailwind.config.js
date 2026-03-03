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
      },
      keyframes: {
        'fade-slide-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        'fade-scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' }
        },
        'slide-up-spring': {
          '0%': { opacity: '0', transform: 'translateY(80px)' },
          '60%': { opacity: '1', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        'pulse-scale': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.05)' }
        }
      },
      animation: {
        'fade-slide-up': 'fade-slide-up 0.3s ease-out both',
        'fade-scale-in': 'fade-scale-in 0.3s ease-out both',
        'slide-up-spring': 'slide-up-spring 0.5s cubic-bezier(0.22,1,0.36,1) both',
        'pulse-scale': 'pulse-scale 4s ease-in-out infinite'
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
};
