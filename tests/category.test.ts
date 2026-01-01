import { describe, it, expect } from 'vitest';
import { getNextCategory } from '../src/llm';

describe('Logic: Category Rotation', () => {
    it('rotates through categories deterministically', async () => {
        // Mock Env and KV
        let storedIndex = '0';
        const mockEnv = {
            ASSETS_KV: {
                get: async (key: string) => storedIndex,
                put: async (key: string, val: string) => { storedIndex = val; }
            }
        } as any;

        // Collect a sequence categories
        const sequence: string[] = [];
        for (let i = 0; i < 15; i++) {
            sequence.push(await getNextCategory(mockEnv));
        }

        // Must not be all same
        const unique = new Set(sequence);
        expect(unique.size).toBeGreaterThan(1);
        expect(unique.size).toBeLessThanOrEqual(5); // We have 5 categories

        // Should repeat pattern every 5 items
        expect(sequence[0]).toBe(sequence[5]);
        expect(sequence[1]).toBe(sequence[6]);
        expect(sequence[0]).not.toBe(sequence[1]);
    });
});
