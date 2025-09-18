/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.{html,htm}",
    "./api/**/*.{js,ts,py}",
    "./prompts/**/*.md",
    "./example_outputs/**/*.json"
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
