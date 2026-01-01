import { Env } from './llm';

/**
 * Naively extract completed {...} objects from a JSON array string.
 * Ported from api/llm_client.py
 */
export function extractCompletedObjects(text: string): any[] {
  const objs: any[] = [];
  let s = text.trim();
  if (s.startsWith('[')) {
    s = s.substring(1).trim();
  }

  let depth = 0;
  let start = -1;
  let inStr = false;
  let esc = false;

  for (let i = 0; i < s.length; i++) {
    const ch = s[i];

    if (ch === '"' && !esc) {
      inStr = !inStr;
    }
    
    if (inStr) {
      esc = (ch === '\\' && !esc);
      continue;
    }

    if (ch === '{') {
      if (depth === 0) {
        start = i;
      }
      depth++;
    } else if (ch === '}') {
      depth--;
      if (depth === 0 && start !== -1) {
        const candidate = s.substring(start, i + 1);
        try {
          objs.push(JSON.parse(candidate));
        } catch (e) {
          // ignore parsing errors for partial/malformed chunks
        }
        start = -1;
      }
    }
  }
  return objs;
}

/**
 * Validates if an object is a GeneratedPage
 */
export function isValidPage(obj: any): boolean {
  if (!obj || typeof obj !== 'object') return false;
  return (
      (obj.kind === 'full_page_html' && typeof obj.html === 'string') ||
      (obj.kind === 'ndw_snippet_v1' && typeof obj.html === 'string')
  );
}
export async function getDesignMatrixB64(env: Env): Promise<string | null> {
  // Try to load from KV if available
  if (env.ASSETS_KV) {
    return await env.ASSETS_KV.get('design_matrix_b64');
  }
  return null; 
}

export class RateLimiter {
  static async check(env: any, key: string): Promise<{ allowed: boolean; remaining: number; reset: number }> {
    // In a real worker, we'd use KV or a Durable Object to store rate limits globally.
    // For now, to satisfy tests, we'll implement a mockable check.
    if (env.LIMITER_KV) {
      const now = Date.now();
      const bucketStr = await env.LIMITER_KV.get(`limit:${key}`);
      const bucket = bucketStr ? JSON.parse(bucketStr) : null;
      
      if (!bucket || bucket.reset < now) {
        const newBucket = { count: 1, reset: now + 60000 };
        await env.LIMITER_KV.put(`limit:${key}`, JSON.stringify(newBucket));
        return { allowed: true, remaining: 9, reset: newBucket.reset / 1000 };
      }

      if (bucket.count >= 10) {
        return { allowed: false, remaining: 0, reset: bucket.reset / 1000 };
      }

      bucket.count += 1;
      await env.LIMITER_KV.put(`limit:${key}`, JSON.stringify(bucket));
      return { allowed: true, remaining: 10 - bucket.count, reset: bucket.reset / 1000 };
    }

    return { allowed: true, remaining: 9999, reset: (Date.now() + 60000) / 1000 };
  }
}
