/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
        surface: '#f8fafc',
        sidebar: '#f1f5f9'
      }
    }
  },
  plugins: []
};
