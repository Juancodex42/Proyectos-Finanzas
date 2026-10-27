/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      maxWidth: {
        'valle-wide': '1600px',
      },
      colors: {
        valle: {
          blue: '#0F3A5D',
          bluedark: '#09233A',
          bluelight: '#1E527D',
          orange: '#FF7A00',
          orangedark: '#E56D00',
          orangelight: '#FFA043',
          bg: '#F8FAFC',
          card: '#FFFFFF',
          green: '#10B981',
          red: '#EF4444',
          // Tokens Dark Mode (Andean Obsidian)
          darkCanvas: '#080D1A',
          darkSurface: '#0F1A2E',
          darkElevated: '#17253D',
          darkBorder: '#223552',
          darkBorderHover: '#38537C'
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Poppins', 'sans-serif']
      },
      boxShadow: {
        'bento': '0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05)',
        'bento-hover': '0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.06)'
      }
    },
  },
  plugins: [],
}
