/** @type {import('tailwindcss').Config} */
module.exports = {
content: [
    "./app/templates/**/*.html",
    "./app/static/**/*.js",
],
theme: {
    extend: {
    colors: {
        'family-dark': '#0f172a',
        'glass-white': 'rgba(255, 255, 255, 0.05)',
    },
    backdropBlur: {
        'glass': '16px',
    }
    },
},
plugins: [],
}