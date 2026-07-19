/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        /**
         * HTML templates inside your root templates directory and app directories.
         */
        '../templates/**/*.html',
        '../../templates/**/*.html',
        '../../**/templates/**/*.html',
    ],
    theme: {
        extend: {},
    },
    plugins: [
        require('@tailwindcss/typography'),
        require('@tailwindcss/forms'),
        require('@tailwindcss/aspect-ratio'),
        require('daisyui'),
    ],
}