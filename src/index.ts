import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { streamSSE } from 'hono/streaming';
import * as llm from './llm';
import { RateLimiter } from './utils';

// Types for Cloudflare bindings
interface Env {
  ASSETS_KV: KVNamespace;
  DEDUPE_KV: KVNamespace;
  QUEUE_DO: DurableObjectNamespace;
  MODEL_NAME: string;
  GROQ_API_KEY: string;
  OPENROUTER_API_KEY: string;
  GEMINI_API_KEY: string;
  LIMITER_KV: KVNamespace;
  PYTHON_BACKEND_URL: string;
}

const app = new Hono<{ Bindings: Env }>();

// CORS middleware
app.use('*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'X-API-Key'],
}));

// Health check
app.get('/health', (c) => c.json({ status: 'ok', runtime: 'cloudflare-workers' }));

// Metrics endpoint
app.get('/metrics/total', async (c) => {
  const count = await c.env.ASSETS_KV.get('generation_count');
  return c.json({ total: parseInt(count || '0', 10) });
});

// Generate endpoint (sync - returns first from queue or generates)
app.post('/generate', async (c) => {
  try {
    const body = await c.req.json();
    const seed = body.seed || Math.floor(Math.random() * 1e9);
    const brief = body.brief || '';

    // Rate Limit Check
    const apiKey = c.req.header('X-API-Key') || 'anonymous';
    const limit = await RateLimiter.check(c.env, apiKey);
    if (!limit.allowed) {
      c.header('Retry-After', String(Math.floor(limit.reset - Date.now() / 1000)));
      return c.json({ error: 'rate limit exceeded' }, 429);
    }
    
    // Try to get from prefetch queue first
    const queueId = c.env.QUEUE_DO.idFromName('global');
    const queue = c.env.QUEUE_DO.get(queueId);
    
    const queueResp = await queue.fetch(new Request('http://do/dequeue', { method: 'POST' }));
    
    if (queueResp.ok) {
      const page = await queueResp.json();
      await incrementCounter(c.env.ASSETS_KV);
      return c.json(page);
    }
    
    // Queue empty - generate ad-hoc using real LLM
    const iterator = llm.generatePageBurst(c.env, seed, brief);
    const first = await iterator.next();
    
    if (first.done || !first.value) {
      throw new Error('No pages generated');
    }
    
    const page = first.value;
    await incrementCounter(c.env.ASSETS_KV);
    const PAGE_SHAPE_HINT = `
- RETURN A COMPLETE HTML STRING in the "html" field. This string MUST include:
    1. A <style> block with unique, premium CSS (using Tailwind classes where possible, but custom CSS for animations/glassmorphism).
    2. The main container <div id="ndw-content">.
    3. A <script> block containing all the interactive logic (GSAP animations, event listeners, etc.).
- GSAP 3.12, Tailwind CSS, and Lucide Icons are provided globally. Do NOT import them.
- Use Lucide icons: <i data-lucide="name"></i> and call lucide.createIcons() in your script.
- NO PLACEHOLDER IMAGES. Use CSS gradients, patterns, or SVG.
- INTERACTIVE QUALITY: The experience MUST be playable. If it's a toy, it must have working buttons/sliders.
- DEFENSIVE JAVASCRIPT:
    1. Always check element existence: const el = document.getElementById("..."); if (el) { ... }
    2. Wrap your entire logic in a try/catch block.
    3. Use window.addEventListener('DOMContentLoaded') and ensure logic runs even if the DOM is already ready.
- AESTHETICS: Use vibrant gradients, subtle shadows, and smooth transitions. Avoid the "default" look.
- Return ONLY valid JSON.
`;
    
    // Efficiency: Capture remaining pages in the burst and enqueue them
    c.executionCtx.waitUntil((async () => {
      for await (const extra of iterator) {
        if (extra) {
          await queue.fetch(new Request('http://do/enqueue', {
            method: 'POST',
            body: JSON.stringify(extra)
          }));
        }
      }
    })());

    return c.json(page);
    
  } catch (err) {
    console.error('Generate error:', err);
    return c.json({ error: String(err) }, 500);
  }
});

// Streaming generate endpoint (NDJSON)
app.post('/generate/stream', async (c) => {
  const body = await c.req.json();
  const brief = body.brief || '';
  const seed = body.seed || Math.floor(Math.random() * 1e9);
  
  // Rate Limit Check
  const apiKey = c.req.header('X-API-Key') || 'anonymous';
  const limit = await RateLimiter.check(c.env, apiKey);
  if (!limit.allowed) {
    return c.json({ error: 'rate limit exceeded' }, 429);
  }

  // Helper to send formatted SSE
  let controller: ReadableStreamDefaultController;
  const sendEvent = (event: string, data: any) => {
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    try {
      controller.enqueue(new TextEncoder().encode(payload));
    } catch (e) { /* ignore */ }
  };

  return new Response(new ReadableStream({
    async start(ctrl) {
      controller = ctrl;
      
      try {
        // Heartbeat (4KB padding)
        const heartbeat = setInterval(() => {
          try {
             const padding = ' '.repeat(4096); 
             controller.enqueue(new TextEncoder().encode(`: heartbeat ${padding}\n\n`));
          } catch(e) { clearInterval(heartbeat); }
        }, 10000); 

        // 1. Try Queue (Prefetch)
        let handled = false;
        if (!brief.trim()) {
           const queueId = c.env.QUEUE_DO.idFromName('global');
           const queue = c.env.QUEUE_DO.get(queueId);
           
           // Check Threshold (250)
           const sizeResp = await queue.fetch(new Request('http://do/size'));
           const { size } = await sizeResp.json() as { size: number };
           const QUEUE_THRESHOLD = 250;
           
           if (size >= QUEUE_THRESHOLD) {
             const resp = await queue.fetch(new Request('http://do/dequeue', { method: 'POST' }));
             if (resp.ok) {
               const page = await resp.json();
               clearInterval(heartbeat);
               sendEvent('meta', { status: 'ready', model: 'prefetched' });
               sendEvent('page', page);
               sendEvent('done', {});
               controller.close();
               
               // Increment global counter
               await incrementCounter(c.env.ASSETS_KV);
               return; 
             }
           }
        }
        
        // 2. Python Proxy Fallback
        // If queue low/empty and no brief, use Python for reliability
        if (!handled && !brief.trim() && c.env.PYTHON_BACKEND_URL) {
           console.log('Queue low, proxying to Python backend');
           try {
             const pythonResp = await fetch(`${c.env.PYTHON_BACKEND_URL}/generate`, {
               method: 'POST',
               headers: { 'Content-Type': 'application/json' },
               body: JSON.stringify({ seed, brief })
             });
             
             if (pythonResp.ok) {
                const page = await pythonResp.json();
                clearInterval(heartbeat);
                sendEvent('meta', { status: 'ready', model: 'python-proxy' });
                sendEvent('page', page);
                sendEvent('done', {});
                controller.close();
                await incrementCounter(c.env.ASSETS_KV);
                return;
             }
           } catch (err) {
             console.error('Python proxy failed, falling back to local:', err);
           }
        }

        // 3. Local Generation Fallback
        // (Runs if brief provided OR Python failed)
        const iterator = llm.generatePageBurst(c.env, seed, brief);
        let count = 0;
        
        for await (const page of iterator) {
          if (page) {
            count++;
            if (count === 1) {
              sendEvent('meta', { status: 'generating', model: c.env.MODEL_NAME });
              sendEvent('page', page);
              sendEvent('done', {});
            }
            // Enqueue extras if random gen
            if (count > 1 && !brief) {
              const p = page;
              c.executionCtx.waitUntil((async () => {
                const queueId = c.env.QUEUE_DO.idFromName('global');
                const queue = c.env.QUEUE_DO.get(queueId);
                await queue.fetch(new Request('http://do/enqueue', {
                  method: 'POST',
                  body: JSON.stringify(p)
                }));
              })());
            }
            await incrementCounter(c.env.ASSETS_KV);
          }
        }
        
        clearInterval(heartbeat);
        if (count === 0) sendEvent('error', { error: 'No pages generated' });
        controller.close();

      } catch (err) {
        console.error('Stream error:', err);
        sendEvent('error', { error: String(err) });
      }
    }
  }), {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    }
  });
});

// Helper: Increment generation counter
async function incrementCounter(kv: KVNamespace): Promise<void> {
  const current = parseInt(await kv.get('generation_count') || '0', 10);
  await kv.put('generation_count', String(current + 1));
}

// Scheduled prefetcher (runs every minute)
app.get('/prefetch/size', async (c) => {
  const queueId = c.env.QUEUE_DO.idFromName('global');
  const queue = c.env.QUEUE_DO.get(queueId);
  const resp = await queue.fetch(new Request('http://do/size'));
  return resp;
});

// Worker entry point
export default {
  fetch: app.fetch,
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext) {
    console.log('Cron Triggered: Keep-Alive Only');
    
    // 1. Keep Python backend warm
    if (env.PYTHON_BACKEND_URL) {
      try {
        await fetch(`${env.PYTHON_BACKEND_URL}/health`);
        console.log('Pinged Python backend for keep-alive');
      } catch (e) {
        console.error('Keep-alive ping failed', e);
      }
    }
    
    // 2. Auto-refill is DISABLED for now
    // We rely on manual pre-filling to protect Render/Gemini quotas.
    // The "refill" logic has been removed to ensure zero interference.
  }
};

// Export the Durable Object class
export { PrefetchQueue } from './queue-do';
