import { defineWorkersProject } from '@cloudflare/vitest-pool-workers/config';
import { defineConfig, defineWorkspace } from 'vitest/config';

export default defineWorkspace([
  {
    test: {
      name: 'node',
      environment: 'node',
      include: ['tests/runtime.test.ts'],
    },
  },
  defineWorkersProject({
    test: {
      name: 'workers',
      include: ['tests/**/*.test.ts'],
      exclude: ['tests/runtime.test.ts'],
      poolOptions: {
        workers: {
          wrangler: { configPath: './wrangler.test.toml' },
          isolatedStorage: false,
        },
      },
    },
  }),
]);
