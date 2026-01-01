import { describe, it, expect, vi, beforeEach } from 'vitest';
import { generatePage } from '../src/llm';

describe('Logic: Provider Fallback & Order', () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    beforeEach(() => {
        mockFetch.mockReset();
    });

    const mockEnv = {
        GROQ_API_KEY: 'groq-key',
        OPENROUTER_API_KEY: 'openrouter-key',
        GEMINI_API_KEY: '',
        DEDUPE_KV: { get: async () => null, put: async () => {} } as any,
        ASSETS_KV: { get: async () => '0', put: async () => {} } as any
    };

    it('prefers OpenRouter over Groq when both are present', async () => {
        // OpenRouter succeeds
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({
                choices: [{ message: { content: '{"kind": "full_page_html", "html": "OPENROUTER"}' } }]
            })
        });

        const result = await generatePage(mockEnv as any, 123);
        
        expect(result.html).toBe('OPENROUTER');
        // fetch should only have been called once (for OpenRouter)
        expect(mockFetch).toHaveBeenCalledTimes(1);
        expect(mockFetch.mock.calls[0][0]).toContain('openrouter.ai');
    });

    it('falls back to Groq when OpenRouter fails', async () => {
        // 1. OpenRouter failures (it retries internally 3 times)
        const failParams = { ok: false, status: 500, text: () => Promise.resolve('Error') };
        mockFetch.mockResolvedValueOnce(failParams); // devstral
        mockFetch.mockResolvedValueOnce(failParams); // gemini
        mockFetch.mockResolvedValueOnce(failParams); // deepseek

        // 2. Groq succeeds
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({
                choices: [{ message: { content: '{"kind": "full_page_html", "html": "GROQ"}' } }]
            })
        });

        const result = await generatePage(mockEnv as any, 123);
        
        expect(result.html).toBe('GROQ');
        expect(mockFetch).toHaveBeenCalledTimes(4);
        expect(mockFetch.mock.calls[0][0]).toContain('openrouter.ai');
        // skip middle ones
        expect(mockFetch.mock.calls[3][0]).toContain('groq.com');
    });

    it('hits the correct Groq endpoint with expected body structure', async () => {
        const groqOnlyEnv = { ...mockEnv, OPENROUTER_API_KEY: '' };
        
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({
                choices: [{ message: { content: '{"kind": "full_page_html", "html": "OK"}' } }]
            })
        });

        await generatePage(groqOnlyEnv as any, 42, 'test brief');

        const [url, init] = mockFetch.mock.calls[0];
        expect(url).toBe('https://api.groq.com/openai/v1/chat/completions');
        
        const body = JSON.parse(init.body);
        expect(body.model).toBeDefined();
        expect(body.messages).toHaveLength(2);
        expect(body.seed).toBe(42);
    });
});
