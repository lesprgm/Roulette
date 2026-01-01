import { env, createExecutionContext, waitOnExecutionContext, SELF } from 'cloudflare:test';
import { describe, it, expect, vi } from 'vitest';
import worker from '../src/index';

// Mock the LLM generation module completely for route testing
vi.mock('../src/llm', async (importOriginal) => {
  return {
    generatePageBurst: async function* () {
      yield {
        kind: 'full_page_html',
        html: '<html>Mocked Page</html>',
        title: 'Mock Title',
        seed: 12345,
        category: 'Test Category'
      };
    }
  };
});

describe('Worker Routes (Integrated)', () => {
  it('GET /health returns ok', async () => {
    const resp = await worker.fetch(
      new Request('http://example.com/health'),
      env,
      createExecutionContext()
    );
    expect(resp.status).toBe(200);
    const json = await resp.json() as any;
    expect(json).toEqual({ status: 'ok', runtime: 'cloudflare-workers' });
  });

  it('POST /generate returns a page (mocked LLM)', async () => {
    const resp = await worker.fetch(
      new Request('http://example.com/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed: 123 })
      }),
      env,
      createExecutionContext()
    );
    
    expect(resp.status).toBe(200);
    const page = await resp.json() as any;
    expect(page.kind).toBe('full_page_html');
    expect(page.seed).toBe(12345); // Should match our mock
  });

  it('GET /metrics/total increments', async () => {
    // Check initial
    let resp = await worker.fetch(
        new Request('http://example.com/metrics/total'),
        env,
        createExecutionContext()
    );
    let json = await resp.json() as any;
    const initial = json.total;

    // Generate to increment
    await worker.fetch(
        new Request('http://example.com/generate', {
            method: 'POST',
            body: JSON.stringify({})
        }),
        env,
        createExecutionContext()
    );

    // Check after
    resp = await worker.fetch(
        new Request('http://example.com/metrics/total'),
        env,
        createExecutionContext()
    );
    json = await resp.json() as any;
    expect(json.total).toBe(initial + 1);
  });
});
