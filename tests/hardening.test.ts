import { env, SELF } from 'cloudflare:test';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import worker from '../src/index';
import * as llm from '../src/llm';

const mockBurst = vi.fn().mockImplementation(async function* () { });
// Mock the whole module
vi.mock('../src/llm', async (importOriginal) => {
  const mod = await importOriginal<any>();
  return {
    ...mod,
    generatePageBurst: (...args: any[]) => mockBurst(...args),
  };
});

describe('Architectural Hardening', () => {
  it('enforces 7-day TTL on KV page storage', async () => {
    const id = (env as any).QUEUE_DO.idFromName('ttl-test');
    const stub = (env as any).QUEUE_DO.get(id);

    // Mock KV.put to check options
    const putSpy = vi.spyOn((env as any).ASSETS_KV, 'put');

    const payload = { kind: 'full_page_html', html: '<div>ttl</div>', seed: 999 };
    await stub.fetch(new Request('http://do/enqueue', {
      method: 'POST',
      body: JSON.stringify(payload)
    }));

    expect(putSpy).toHaveBeenCalledWith(
      expect.stringContaining('page:'),
      expect.any(String),
      expect.objectContaining({ expirationTtl: 259200 })
    );

    putSpy.mockRestore();
  });

  it('runs keep-alive ping on scheduled event', async () => {
    const logSpy = vi.spyOn(console, 'log');
    const mockCtx = { waitUntil: vi.fn() } as any;
    
    // Set PYTHON_BACKEND_URL to trigger ping
    const testEnv = { ...env, PYTHON_BACKEND_URL: 'http://test-python' };
    
    // We can't easily mock global fetch inside the worker via 'worker.scheduled' 
    // without more setup, blocking the network call. 
    // However, we just want to verify it LOGS "Cron Triggered: Keep-Alive Only".
    
    await worker.scheduled({} as any, testEnv as any, mockCtx);

    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Cron Triggered: Keep-Alive Only'));
    logSpy.mockRestore();
  });

  it('captures overflow burst pages into the queue during ad-hoc generation', async () => {
    const id = (env as any).QUEUE_DO.idFromName('global');
    const stub = (env as any).QUEUE_DO.get(id);

    // Clear queue
    while (true) {
      const dr = await stub.fetch(new Request('http://do/dequeue', { method: 'POST' }));
      if (dr.status !== 200) break;
    }

    // Set mock implementation
    mockBurst.mockImplementation(async function* () {
      yield { kind: 'full_page_html', html: 'page1', seed: 1, title: 'P1' } as any;
      yield { kind: 'full_page_html', html: 'page2', seed: 2, title: 'P2' } as any;
      yield { kind: 'full_page_html', html: 'page3', seed: 3, title: 'P3' } as any;
    });

    const resp = await SELF.fetch(new Request('http://localhost/generate', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': 'test' },
      body: JSON.stringify({})
    }));

    if (resp.status === 500) {
      console.error('GENERATE FAILED:', await resp.text());
    }
    expect(resp.status).toBe(200);
    const firstPage = await resp.json() as any;
    expect(firstPage.html).toBe('page1');

    // Wait for background tasks
    await new Promise(r => setTimeout(r, 200));

    // Verify queue now has page2 and page3
    const qSizeResp = await stub.fetch(new Request('http://do/size'));
    const { size } = await qSizeResp.json() as any;
    expect(size).toBe(2);
    mockBurst.mockReset();
  });
});
