/* eslint-disable no-console */
// Copies runtime vendor assets into `static/vendor/` at build time.
// We keep this tiny and dependency-free so Render can run it during npm build.

const fs = require("fs");
const path = require("path");

function copyIfExists(src, dest) {
  if (!fs.existsSync(src)) {
    console.warn(`[build_vendor] missing: ${src}`);
    return false;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  console.log(`[build_vendor] copied: ${src} -> ${dest}`);
  return true;
}

function main() {
  const root = process.cwd();
  const vendorDir = path.join(root, "static", "vendor");

  // Three.js ESM build (used by tunnel runtime).
  // Source: npm package `three` (installed via npm ci).
  copyIfExists(
    path.join(root, "node_modules", "three", "build", "three.module.js"),
    path.join(vendorDir, "three.module.js")
  );
}

main();

