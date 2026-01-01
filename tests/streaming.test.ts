import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index';
import { RateLimiter } from '../src/utils';
import * as llm from '../src/llm';

describe('API: Streaming & Robustness', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    const mockEnv = {
        ASSETS_KV: { get: async () => '0', put: async () => {} },
        DEDUPE_KV: { get: async () => null, put: async () => {} },
        QUEUE_DO: { 
            idFromName: () => ({ toString: () => 'id' }),
            get: () => ({ fetch: async () => new Response(null, { status: 404 }) }) 
        },
        LIMITER_KV: { get: async () => null, put: async () => {} }
    };

    it('returns 429 when rate limited with Retry-After header', async () => {
        // Mock RateLimiter to return disallowed
        vi.spyOn(RateLimiter, 'check').mockResolvedValue({
            allowed: false,
            remaining: 0,
            reset: 1735150000 // Some future timestamp in seconds
        });

        const req = new Request('http://localhost/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief: 'fast' })
        });

        const res = await app.fetch(req, mockEnv as any);
        
        expect(res.status).toBe(429);
        const data = await res.json() as any;
        expect(data.error).toBe('rate limit exceeded');
        expect(res.headers.has('Retry-After')).toBe(true);
    });

    it('generate endpoint returns ad-hoc page when queue is empty', async () => {
        vi.spyOn(RateLimiter, 'check').mockResolvedValue({ allowed: true, remaining: 10, reset: 0 });
        
        async function* mockGenerator() {
            yield { kind: 'full_page_html', html: 'AD-HOC', seed: 42, title: 'Mock' } as any;
        }
        const burstSpy = vi.spyOn(llm, 'generatePageBurst').mockReturnValue(mockGenerator() as any);

        const req = new Request('http://localhost/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief: 'test' })
        });

        // Hono needs executionCtx if waitUntil is used
        const mockCtx = { waitUntil: vi.fn() };
        const res = await (app as any).fetch(req, mockEnv as any, mockCtx);
        
        expect(res.status).toBe(200);
        const data = await res.json() as any;
        expect(data.html).toBe('AD-HOC');
        
        burstSpy.mockRestore();
    });

    it('generate/stream handles NDJSON events correctly', async () => {
        vi.spyOn(RateLimiter, 'check').mockResolvedValue({ allowed: true, remaining: 10, reset: 0 });
        
        const mockPage = {
            kind: 'full_page_html' as const,
            html: 'STREAMED',
            seed: 99
        };

        // Mock generatePageBurst as an async generator
        async function* mockGenerator() {
            yield mockPage;
        }
        vi.spyOn(llm, 'generatePageBurst').mockReturnValue(mockGenerator() as any);

        const req = new Request('http://localhost/generate/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief: 'stream-test' })
        });

        const res = await app.fetch(req, mockEnv as any);
        expect(res.status).toBe(200);
        expect(res.headers.get('Content-Type')).toContain('text/event-stream');

        const body = await res.text();
        const lines = body.trim().split('\n\n'); // SSE events separated by double newlines
        
        expect(lines.length).toBeGreaterThanOrEqual(2);
        
        // Parse SSE data
        const parseSSE = (line: string) => {
            const dataLine = line.split('\n').find(l => l.startsWith('data: '));
            return dataLine ? JSON.parse(dataLine.replace('data: ', '')) : null;
        };

        const meta = parseSSE(lines[0]);
        // Find the page event (might be meta, then page, then done)
        const pageLine = lines.find(l => l.includes('event: page'));
        const page = parseSSE(pageLine!);

        expect(meta.status).toBe('generating');
        expect(meta.status).toBe('generating');
        expect(page.html).toBe('STREAMED');
    });
});
