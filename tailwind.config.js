/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scan templates, TypeScript sources, compiled JS (for any dynamic injections), and backend templates
  content: [
    "./templates/**/*.html",
    "./static/ts-src/**/*.ts",
    "./api/**/*.py"
  ],
};
