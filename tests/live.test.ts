import { describe, it, expect } from 'vitest';
import { generatePage } from '../src/llm';

describe('Integration: Live API Tests', () => {
    // These tests require real API keys in .env
    // They are skipped by default to avoid accidental token usage.

    it.skip('can generate a real page via Groq', async () => {
        const env = {
            GROQ_API_KEY: process.env.GROQ_API_KEY,
            DEDUPE_KV: { get: async () => null, put: async () => {}, signatureFor: async () => 'sig' }
        } as any;
        
        const result = await generatePage(env, 1234, 'live test');
        expect(result.html).toContain('<!doctype html>');
    });

    it.skip('can generate a real page via OpenRouter', async () => {
        const env = {
            OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY,
            DEDUPE_KV: { get: async () => null, put: async () => {}, signatureFor: async () => 'sig' }
        } as any;
        
        const result = await generatePage(env, 5678, 'live test');
        expect(result.html).toContain('<!doctype html>');
    });

    it.skip('can generate a real page via Gemini', async () => {
        const env = {
            GEMINI_API_KEY: process.env.GEMINI_API_KEY,
            DEDUPE_KV: { get: async () => null, put: async () => {}, signatureFor: async () => 'sig' }
        } as any;
        
        const result = await generatePage(env, 9012, 'live test');
        expect(result.html).toContain('<!doctype html>');
    });
});
