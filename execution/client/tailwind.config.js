/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0b',
        surface: '#111114',
        'surface-2': '#1a1a1f',
        border: '#2a2a30',
        text: '#f4f4f5',
        'text-muted': '#a1a1aa',
        'text-dim': '#71717a',
        accent: '#4ade80',
        ok: '#4ade80',
        warn: '#fbbf24',
        danger: '#f87171',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
