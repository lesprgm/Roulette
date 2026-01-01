/**
 * Structural Deduplication Logic
 * Ports the logic from api/dedupe.py to TypeScript.
 */

export interface DedupeInterface {
  has(sig: string): Promise<boolean>;
  add(sig: string): Promise<void>;
  signatureFor(doc: any): Promise<string>;
}

export class KVDedupe implements DedupeInterface {
  private kv: KVNamespace;
  private maxItems: number;

  constructor(kv: KVNamespace, maxItems = 200) {
    this.kv = kv;
    this.maxItems = maxItems;
  }

  /**
   * Check if a signature exists in the global dedupe set.
   * Note: For simple KV implementation, we might just look up the key directly.
   * Ideally we'd store a set, but KV is key-value. 
   * We will use key = `sig:{hash}` and check existence.
   */
  async has(sig: string): Promise<boolean> {
    if (!sig) return false;
    const val = await this.kv.get(`sig:${sig}`);
    return val !== null;
  }

  async add(sig: string): Promise<void> {
    if (!sig) return;
    // We set a TTL to auto-expire old signatures (e.g., 24 hours) as a simple rolling window
    // implementing exact 200-item LRU on KV is hard without a coordinating object or list.
    // For now, TTL is a robust enough approximation for "recent".
    await this.kv.put(`sig:${sig}`, Date.now().toString(), { expirationTtl: 86400 });
  }

  async signatureFor(doc: any): Promise<string> {
    const payload = this.extractPayload(doc);
    if (!payload) return "";
    
    // Compute SHA-256
    const encoder = new TextEncoder();
    const data = encoder.encode(payload);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  private extractPayload(doc: any): string {
    if (!doc || typeof doc !== 'object') return "";

    if (doc.kind === 'ndw_snippet_v1') {
      return this.skeletonize(doc.html || "") + (doc.css || "") + (doc.js || "");
    }
    
    if (doc.kind === 'full_page_html' && typeof doc.html === 'string') {
      return this.skeletonize(doc.html);
    }

    // Fallback: JSON dump
    try {
      // Sort keys for stability (canonicalization)
      return JSON.stringify(doc, Object.keys(doc).sort());
    } catch {
      return String(doc);
    }
  }

  skeletonize(html: string): string {
    if (!html) return "";
    let s = html;
    
    // 1. Remove comments
    s = s.replace(/<!--[\s\S]*?-->/g, "");
    
    // 2. Remove script and style blocks
    s = s.replace(/<(script|style)[\s\S]*?>[\s\S]*?<\/\1>/gi, "");
    
    // 3. Strip all text between tags: >TEXT< -> ><
    s = s.replace(/>[^<]+</g, "><");
    
    // 4. Strip start/end text
    s = s.replace(/^[^<]+/, "");
    s = s.replace(/[^>]+$/, "");
    
    // Remove whitespace
    s = s.replace(/\s+/g, "");
    
    return s;
  }
}
