import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'url';

const rootDir = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  test: {
    include: ['tests/frontend/**/*.test.ts'],
    environment: 'happy-dom',
  },
  resolve: {
    alias: [
      { find: /^\.\/tunnel\.js$/, replacement: `${rootDir}static/ts-src/tunnel.ts` },
      { find: 'three', replacement: `${rootDir}tests/frontend/mocks/three.ts` },
    ],
  },
});
