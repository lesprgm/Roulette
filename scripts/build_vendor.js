/* eslint-disable no-console */
// Copies runtime vendor assets into `static/vendor/` at build time.
// We keep this tiny and dependency-free so Render can run it during npm build.

const fs = require("fs");
const path = require("path");

function copyIfExists(src, dest, options = {}) {
  if (!fs.existsSync(src)) {
    if (!options.optional) {
      throw new Error(`[build_vendor] missing required source: ${src}`);
    }
    return false;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  console.log(`[build_vendor] copied: ${src} -> ${dest}`);
  return true;
}

function requireAsset(file) {
  if (!fs.existsSync(file)) {
    throw new Error(`[build_vendor] missing required runtime asset after build: ${file}`);
  }
}

function main() {
  const root = process.cwd();
  const vendorDir = path.join(root, "static", "vendor");

  const fontFiles = [
    ["@fontsource/inter/files/inter-latin-400-normal.woff2", "fonts/inter-400.woff2"],
    ["@fontsource/inter/files/inter-latin-700-normal.woff2", "fonts/inter-700.woff2"],
    ["@fontsource/space-grotesk/files/space-grotesk-latin-400-normal.woff2", "fonts/space-grotesk-400.woff2"],
    ["@fontsource/space-grotesk/files/space-grotesk-latin-700-normal.woff2", "fonts/space-grotesk-700.woff2"],
    ["@fontsource/playfair-display/files/playfair-display-latin-400-normal.woff2", "fonts/playfair-display-400.woff2"],
    ["@fontsource/playfair-display/files/playfair-display-latin-700-normal.woff2", "fonts/playfair-display-700.woff2"],
  ];

  for (const [source, target] of fontFiles) {
    copyIfExists(path.join(root, "node_modules", source), path.join(vendorDir, target));
  }

  // Three.js ESM build (used by tunnel runtime).
  // Source: npm package `three` (installed via npm ci).
  copyIfExists(
    path.join(root, "node_modules", "three", "build", "three.module.js"),
    path.join(vendorDir, "three.module.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "three", "examples", "jsm", "controls", "OrbitControls.js"),
    path.join(vendorDir, "three-addons", "controls", "OrbitControls.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "three", "examples", "jsm", "postprocessing", "EffectComposer.js"),
    path.join(vendorDir, "three-addons", "postprocessing", "EffectComposer.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "three", "examples", "jsm", "postprocessing", "RenderPass.js"),
    path.join(vendorDir, "three-addons", "postprocessing", "RenderPass.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "three", "examples", "jsm", "postprocessing", "UnrealBloomPass.js"),
    path.join(vendorDir, "three-addons", "postprocessing", "UnrealBloomPass.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "alpinejs", "dist", "cdn.min.js"),
    path.join(vendorDir, "alpine.min.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "matter-js", "build", "matter.min.js"),
    path.join(vendorDir, "matter.min.js")
  );
  copyIfExists(
    path.join(root, "node_modules", "gsap", "dist", "ScrollTrigger.min.js"),
    path.join(vendorDir, "ScrollTrigger.min.js"),
    { optional: true }
  );

  [
    path.join(vendorDir, "three.module.js"),
    path.join(vendorDir, "three-addons", "controls", "OrbitControls.js"),
    path.join(vendorDir, "three-addons", "postprocessing", "EffectComposer.js"),
    path.join(vendorDir, "three-addons", "postprocessing", "RenderPass.js"),
    path.join(vendorDir, "three-addons", "postprocessing", "UnrealBloomPass.js"),
    path.join(vendorDir, "alpine.min.js"),
    path.join(vendorDir, "matter.min.js"),
    path.join(vendorDir, "gsap.min.js"),
    path.join(vendorDir, "lucide.min.js"),
    path.join(vendorDir, "tailwind-play.js"),
  ].forEach(requireAsset);
}

main();
