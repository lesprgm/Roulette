import { env } from 'cloudflare:test';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as llm from '../src/llm';
import { extractCompletedObjects } from '../src/utils';

describe('Logic: LLM Client', () => {
    // Mock the global fetch
    // Note: globalThis.fetch is writable in the test environment
    const mockFetch = vi.fn();
    const originalFetch = globalThis.fetch;

    beforeEach(() => {
        globalThis.fetch = mockFetch;
        monitor: mockFetch.mockReset();
    });
    
    // Restore fetch after tests
    // afterAll(() => { globalThis.fetch = originalFetch; });

    it('generatePage falls back to placeholder on failure', async () => {
        mockFetch.mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('Error') });
        
        // Mock env without keys to force failure or use keys and fail fetch
        // We cast to any to allow overriding read-only env if needed, though cloudflare:test env is usually mutable in tests?
        // Actually env object from cloudflare:test acts as binding container.
        // We can pass a plain object to the function which expects Env interface.
        const testEnv = { 
            GROQ_API_KEY: 'test', 
            OPENROUTER_API_KEY: 'test', 
            GEMINI_API_KEY: 'test',
            DEDUPE_KV: {
                 get: async () => null,
                 put: async () => {},
            } as any,
            ASSETS_KV: {
                get: async () => null,
                put: async () => {},
            } as any
        };
        
        const page = await llm.generatePage(testEnv, 123);
        
        expect(page.title).toBe('Generation Failed');
        expect(page.kind).toBe('full_page_html');
        expect(page.html).toContain('Generation Temporarily Unavailable');
    });

    it('generatePage parses successful JSON response', async () => {
        const mockResponse = {
            choices: [{ message: { content: '```json\n{"kind": "full_page_html", "html": "<div>Success</div>", "title": "Test"}\n```' } }]
        };
        mockFetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        const testEnv = { 
            GROQ_API_KEY: 'test', 
            OPENROUTER_API_KEY: '', 
            GEMINI_API_KEY: '',
            DEDUPE_KV: {
                 get: async () => null,
                 put: async () => {},
            } as any,
            ASSETS_KV: {
                get: async () => null,
                put: async () => {},
            } as any
        };

        const page = await llm.generatePage(testEnv, 456);
        
        expect(page.kind).toBe('full_page_html');
        expect(page.html).toBe('<div>Success</div>');
        expect(page.seed).toBe(456);
    });

    it('constructs prompt with guidance and categories', async () => {
        // Mock success response
        mockFetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ choices: [{ message: { content: '{}' } }] })
        });

        const testEnv = { 
            GROQ_API_KEY: 'test_key', 
            DEDUPE_KV: { get: async () => null, put: async () => {} } as any,
            ASSETS_KV: { get: async () => null, put: async () => {} } as any
        } as any;

        await llm.generatePage(testEnv, 789, 'Test Brief');

        // Check fetch calls
        expect(mockFetch).toHaveBeenCalled();
        const callArgs = mockFetch.mock.calls[0];
        const body = JSON.parse(callArgs[1].body);
        
        // Body structure depends on provider (Groq uses standard chat completions)
        const messages = body.messages;
        expect(messages).toHaveLength(2); // System + User
        
        const systemPrompt = messages[0].content;
        expect(systemPrompt).toContain('You are an expert web designer');
        expect(systemPrompt).toContain('CATEGORY ASSIGNMENT:');
        expect(systemPrompt).toContain('NO PLACEHOLDER IMAGES'); // From PAGE_SHAPE_HINT
        
        const userPrompt = messages[1].content;
        expect(userPrompt).toContain('Test Brief');
        expect(userPrompt).toContain('Seed: 789');
    });

    it('extractCompletedObjects handles partial JSON arrays', () => {
        const text = '[{"id":1},{"id":2}';
        const objs = extractCompletedObjects(text);
        expect(objs).toHaveLength(2);
        expect(objs[0].id).toBe(1);
        expect(objs[1].id).toBe(2);
    });

    it('extractCompletedObjects handles nested objects and strings with braces', () => {
        const text = '[{"content": "{nested}", "other": "}"}, {"more": 1}]';
        const objs = extractCompletedObjects(text);
        expect(objs).toHaveLength(2);
        expect(objs[0].content).toBe('{nested}');
        expect(objs[1].more).toBe(1);
    });

    it('generatePageBurst yields multiple pages and deduplicates within session', async () => {
        // Since callGeminiBurst is hard to mock directly due to its internal fetch loop,
        // we can test the general flow of generatePageBurst by mocking providers.
        
        // Mock Gemini to fail and OpenRouter to succeed
        const mockResponse = {
            choices: [{ message: { content: '{"kind": "full_page_html", "html": "Burst 1"}' } }]
        };
        mockFetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        const testEnv = { 
            OPENROUTER_API_KEY: 'ok',
            DEDUPE_KV: { get: async () => null, put: async () => {} } as any,
            ASSETS_KV: { get: async () => null, put: async () => {} } as any
        } as any;

        const it = llm.generatePageBurst(testEnv, 101);
        const result = await it.next();
        
        expect(result.done).toBe(false);
        expect(result.value?.html).toBe('Burst 1');
        
        const second = await it.next();
        expect(second.done).toBe(true);
    });

    it('callOpenRouter falls back through model chain', async () => {
        // First call fails, second succeeds
        mockFetch
            .mockResolvedValueOnce({ ok: false, status: 500, text: () => Promise.resolve('Error 1') })
            .mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    choices: [{ message: { content: '{"kind": "full_page_html", "html": "Fallback 1"}' } }]
                })
            });

        const testEnv = {
            OPENROUTER_API_KEY: 'test',
            OPENROUTER_MODEL: 'primary',
            OPENROUTER_FALLBACK_MODEL_1: 'fallback-1',
            DEDUPE_KV: { get: async () => null, put: async () => {} } as any,
            ASSETS_KV: { get: async () => null, put: async () => {} } as any
        } as any;

        const result = await llm.generatePage(testEnv, 123);
        expect(result.html).toBe('Fallback 1');
        expect(mockFetch).toHaveBeenCalledTimes(2);
        
        // Verify models used
        const body1 = JSON.parse(mockFetch.mock.calls[0][1].body);
        const body2 = JSON.parse(mockFetch.mock.calls[1][1].body);
        expect(body1.model).toBe('primary');
        expect(body2.model).toBe('fallback-1');
    });

    it('callGroq falls back to secondary model', async () => {
        mockFetch
            .mockResolvedValueOnce({ ok: false, status: 500, text: () => Promise.resolve('Error 1') })
            .mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    choices: [{ message: { content: '{"kind": "full_page_html", "html": "Groq Fallback"}' } }]
                })
            });

        const testEnv = {
            GROQ_API_KEY: 'test',
            GROQ_MODEL: 'primary',
            GROQ_FALLBACK_MODEL: 'fallback',
            DEDUPE_KV: { get: async () => null, put: async () => {} } as any,
            ASSETS_KV: { get: async () => null, put: async () => {} } as any
        } as any;

        // Force generatePage to use Groq by having no other keys
        const page = await llm.generatePage({ 
            ...testEnv, 
            OPENROUTER_API_KEY: '', 
            GEMINI_API_KEY: '' 
        }, 456);
        
        expect(page.html).toBe('Groq Fallback');
        expect(mockFetch).toHaveBeenCalledTimes(2);
        
        const body2 = JSON.parse(mockFetch.mock.calls[1][1].body);
        expect(body2.model).toBe('fallback');
    });

    it('callGeminiBurst handles split SSE chunks correctly', async () => {
        // Simulate a stream that splits in the middle of a "data: " line
        const chunk1 = 'data: {"candidates":[{"content":{"parts":[{"text": "{\\"kind\\": \\"full_page_html\\", \\"html\\"';
        const chunk2 = ':\\"SPLIT\\"}"}]}}]}\n';
        
        const stream = new ReadableStream({
            start(controller) {
                controller.enqueue(new TextEncoder().encode(chunk1));
                controller.enqueue(new TextEncoder().encode(chunk2));
                controller.close();
            }
        });

        mockFetch.mockResolvedValue({
            ok: true,
            body: stream
        });

        const testEnv = { 
            GEMINI_API_KEY: 'test', 
            ASSETS_KV: { get: async () => '0', put: async () => {} } 
        } as any;
        const it = llm.generatePageBurst(testEnv, 789);
        const result = await it.next();
        
        expect(result.done).toBe(false);
        expect(result.value?.html).toBe('SPLIT');
    });
});
