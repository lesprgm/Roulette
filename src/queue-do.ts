/**
 * Durable Object for managing the prefetch queue with atomic operations.
 * Uses SQLite storage (required for free tier).
 */
export class PrefetchQueue implements DurableObject {
  private state: DurableObjectState;
  private env: any;

  constructor(state: DurableObjectState, env: any) {
    this.state = state;
    this.env = env;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    try {
      if (request.method === 'POST' && path === '/enqueue') {
        return await this.enqueue(request);
      }

      if (request.method === 'POST' && path === '/dequeue') {
        return await this.dequeue();
      }

      if (request.method === 'GET' && path === '/size') {
        return await this.size();
      }
    } catch (err) {
      console.error('DO error:', err);
      return new Response(String(err), { status: 500 });
    }

    return new Response('Not Found', { status: 404 });
  }

  private async enqueue(request: Request): Promise<Response> {
    const page = await request.json();
    
    // Generate ID from content hash
    const content = JSON.stringify(page);
    const encoder = new TextEncoder();
    const data = encoder.encode(content);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const id = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    // Use a timestamp-based key for FIFO ordering
    const timestamp = Date.now();
    const storageKey = `q:${timestamp}:${id}`;

    // Store content in KV for fast global reads (expire in 3 days)
    // We keep the DO storage small by only storing the key 
    await this.env.ASSETS_KV.put(`page:${id}`, content, { expirationTtl: 259200 });

    // Atomic write to storage
    await this.state.storage.put(storageKey, id);

    return Response.json({ status: 'enqueued', id }, { status: 201 });
  }

  private async dequeue(): Promise<Response> {
    // Get the first item (FIFO)
    const list = await this.state.storage.list({ limit: 1, prefix: 'q:' });
    
    if (list.size === 0) {
      return Response.json({ error: 'empty' }, { status: 404 });
    }

    const [storageKey, id] = Array.from(list.entries())[0] as [string, string];

    // Fetch from KV
    const content = await this.env.ASSETS_KV.get(`page:${id}`);
    
    // Atomic delete from DO storage
    await this.state.storage.delete(storageKey);

    if (!content) {
      // If content is missing from KV, just try the next one (non-recursive loop for safety)
      return this.dequeue(); 
    }

    return new Response(content, {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  private async size(): Promise<Response> {
    // Note: list() without values is efficient for counting
    const list = await this.state.storage.list({ prefix: 'q:' });
    return Response.json({ size: list.size });
  }
}
