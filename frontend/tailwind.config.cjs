/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      boxShadow: {
        soft: '0 10px 30px -10px rgba(0,0,0,0.15)'
      },
      borderRadius: {
        xl: '1rem',
      }
    },
  },
  plugins: [require('@tailwindcss/forms')],
}


