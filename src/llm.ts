/**
 * LLM Client for Cloudflare Workers
 * Handles generation via Groq, OpenRouter, and Gemini APIs.
 */

export interface Env {
  GROQ_API_KEY: string;
  OPENROUTER_API_KEY: string;
  GEMINI_API_KEY: string;
  DEDUPE_KV: KVNamespace;
  LIMITER_KV?: KVNamespace;
  ASSETS_KV: KVNamespace;
  GEMINI_REVIEW_ENABLED?: boolean;
  GROQ_MODEL?: string;
  GROQ_FALLBACK_MODEL?: string;
  OPENROUTER_MODEL?: string;
  OPENROUTER_FALLBACK_MODEL_1?: string;
  OPENROUTER_FALLBACK_MODEL_2?: string;
  GEMINI_GENERATION_MODEL?: string;
  GEMINI_REVIEW_MODEL?: string;
}

export type GeneratedPage = {
  kind: 'full_page_html';
  html: string;
  title?: string;
  category?: string;
  seed: number;
} | {
  kind: 'ndw_snippet_v1';
  html: string;
  title?: string;
  css?: string;
  js?: string;
  background?: {
    style?: string;
    class?: string;
  };
  category?: string;
  seed: number;
};

// Category rotation
const CATEGORIES = [
  'Interactive Entertainment / Web Toy',
  'Utility Micro-Tool',
  'Generative Randomizer',
  'Interactive Art',
  'Quizzes / Learning Cards',
];

export async function getNextCategory(env: Env): Promise<string> {
  const kv = env.ASSETS_KV;
  const currentIdxStr = await kv.get('category_index');
  let currentIdx = parseInt(currentIdxStr || '0', 10);
  
  const cat = CATEGORIES[currentIdx % CATEGORIES.length];
  
  // Persist next index
  await kv.put('category_index', String(currentIdx + 1));
  
  return cat;
}

// Core prompt template (simplified version of _PAGE_SHAPE_HINT)
const PAGE_SHAPE_HINT = `
- RETURN A COMPLETE HTML STRING in the "html" field. This string MUST include:
    1. A <style> block with unique, premium CSS (glassmorphism, animations, etc.).
    2. The main container <div id="ndw-content">.
    3. A <script> block containing all logic (event listeners, GSAP, Lucide).
- GSAP 3.12, Tailwind CSS, and Lucide Icons are provided globally. Do NOT import them.
- Use Lucide icons: <i data-lucide="name"></i> and call lucide.createIcons() in your script.
- NO PLACEHOLDER IMAGES. Use CSS gradients or patterns.
- INTERACTIVE QUALITY: The experience MUST be playable with working buttons/sliders.
- DEFENSIVE JAVASCRIPT:
    1. Check element existence: const el = document.getElementById("..."); if (el) { ... }
    2. Wrap your entire logic in a try/catch block.
- Return ONLY valid JSON.
`;

const VISION_GROUNDING_PROMPT = `
VISION GROUNDING: DESIGN MATRIX ATTACHED.
The user has provided a design matrix image containing various professional layout and style patterns.
Keywords: Professional, Playful, Brutalist, Cozy, Minimalist, High-Tech.
You MUST draw inspiration from these patterns to create a premium experience.
`;

import { KVDedupe } from './dedupe';
import { getDesignMatrixB64 } from './utils';

/**
 * Generate a single page. Now wraps generatePageBurst for consistency.
 */
export async function generatePage(env: Env, seed: number, brief: string = ''): Promise<GeneratedPage> {
  const iterator = generatePageBurst(env, seed, brief);
  const first = await iterator.next();
  
  if (first.done || !first.value) {
    return {
      kind: 'full_page_html',
      html: createFallbackHtml('Error', seed),
      title: 'Generation Failed',
      category: 'Error',
      seed,
    };
  }
  
  return first.value;
}

/**
 * Generate multiple pages in a burst.
 */
export async function* generatePageBurst(env: Env, seed: number, brief: string = ''): AsyncGenerator<GeneratedPage> {
  const dedupe = new KVDedupe(env.DEDUPE_KV);
  const category = await getNextCategory(env);
  const categoryNote = `CATEGORY ASSIGNMENT: ${category}. You MUST create an experience in this category.`;
  
  const systemPrompt = `You are an expert web designer creating unique, interactive experiences.
${categoryNote}

${PAGE_SHAPE_HINT}`;

  const userPrompt = brief 
    ? `Create a ${category} experience about: ${brief}. Seed: ${seed}`
    : `Create a unique, creative ${category} experience. Seed: ${seed}`;

  // Priority 1: Gemini Triple-Burst (only if enabled and key exists)
  if (env.GEMINI_API_KEY) {
    const burstSystem = `${systemPrompt}\n\n${VISION_GROUNDING_PROMPT}\nTRIPLE-BURST: You MUST generate exactly 3 distinct websites/activities in a single JSON array [\n  {...},\n  {...},\n  {...}\n]. Each one must follow the formatting rules.`;
    const imageB64 = await getDesignMatrixB64(env);
    
    try {
      const iterator = callGeminiBurst(env, burstSystem, userPrompt, seed, imageB64);
      let pageCount = 0;
      for await (let page of iterator) {
        if (page) {
          pageCount++;
          // Latency Optimization: Skip review for the FIRST page in an ad-hoc burst
          // so the user sees something immediately. Prefetched sites (2, 3) 
          // are still reviewed for quality.
          if (pageCount > 1) {
            const reviewed = await maybeRunComplianceReview(env, page, brief, category);
            if (!reviewed) continue; // Rejected by reviewer
            page = reviewed;
          }

          const sig = await dedupe.signatureFor(page);
          if (!(await dedupe.has(sig))) {
            await dedupe.add(sig);
            page.category = category;
            yield page;
          }
        }
      }
      return; // If Gemini worked, we are done
    } catch (err) {
      console.error('Gemini Burst failed:', err);
      // Fallback to other providers
    }
  }

  // Fallback: Ad-hoc single generation from other providers
  let result: GeneratedPage | null = null;
  if (env.OPENROUTER_API_KEY) {
    result = await callOpenRouter(env, systemPrompt, userPrompt, seed);
  }
  if (!result && env.GROQ_API_KEY) {
    result = await callGroq(env, systemPrompt, userPrompt, seed);
  }

  if (result) {
    // Verify with Reviewer
    const reviewed = await maybeRunComplianceReview(env, result, brief, category);
    if (!reviewed) return; // Rejected
    result = reviewed;

    const sig = await dedupe.signatureFor(result);
    if (!(await dedupe.has(sig))) {
      await dedupe.add(sig);
      result.category = category;
      result.seed = seed;
      yield result;
    }
  }
}

import { extractCompletedObjects } from './utils';

async function* callGeminiBurst(env: Env, system: string, user: string, seed: number, imageB64: string | null): AsyncGenerator<GeneratedPage> {
  const model = env.GEMINI_GENERATION_MODEL || 'gemini-1.5-flash';
  const contents: any[] = [
    {
      role: 'user',
      parts: [
        { text: `${system}\n\n${user}` }
      ]
    }
  ];

  if (imageB64) {
    contents[0].parts.push({
      inlineData: {
        mimeType: 'image/jpeg',
        data: imageB64
      }
    });
  }

  const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:streamGenerateContent?alt=sse&key=${env.GEMINI_API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents,
      generationConfig: {
        temperature: 1.2,
        maxOutputTokens: 64000,
      },
    }),
  });

  if (!resp.ok) {
    throw new Error(`Gemini status ${resp.status} (${model})`);
  }

  const reader = resp.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let fullText = '';
  let seenHashes = new Set<string>();
  let lineBuffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    // SSE parsing: look for "data: " lines with proper line buffering
    lineBuffer += chunk;
    const lines = lineBuffer.split('\n');
    lineBuffer = lines.pop() || ''; // Keep the last partial line in the buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const sseData = JSON.parse(line.substring(6));
          const text = sseData.candidates?.[0]?.content?.parts?.[0]?.text || '';
          fullText += text;
          
          // consuming extract: find the last completed object brace
          let lastBrace = -1;
          let depth = 0;
          let inStr = false;
          let esc = false;

          for (let i = 0; i < fullText.length; i++) {
             const ch = fullText[i];
             if (ch === '"' && !esc) inStr = !inStr;
             if (inStr) { esc = (ch === '\\' && !esc); continue; }
             if (ch === '{') depth++;
             else if (ch === '}') {
               depth--;
               if (depth === 0) lastBrace = i;
             }
          }

          if (lastBrace !== -1) {
             const completePortion = fullText.substring(0, lastBrace + 1);
             // We can't just substring(lastBrace+1) because we might have partial { 
             // for the NEXT object.
             // Actually, the extractCompletedObjects logic handles the whole string.
             // Let's use a better approach: extract, and then trim fullText to only
             // keep the trailing partial part.
             
             const objs = extractCompletedObjects(completePortion);
             for (const obj of objs) {
                const page = validateAndStandardize(obj, seed);
                if (page) {
                   const hash = JSON.stringify(page.html).substring(0, 100);
                   if (!seenHashes.has(hash)) {
                      seenHashes.add(hash);
                      yield page;
                   }
                }
             }
             
             // Keep only what's after the last completed object
             fullText = fullText.substring(lastBrace + 1);
          }
        } catch (e) {
          // Inner JSON might be partial
        }
      }
    }
  }
}

function validateAndStandardize(obj: any, seed: number): GeneratedPage | null {
  if (!obj || typeof obj !== 'object') return null;
  
  if (obj.kind === 'full_page_html' && obj.html) {
    return { ...obj, seed };
  }
  if (obj.kind === 'ndw_snippet_v1' && obj.html) {
    return { ...obj, seed };
  }
  if (obj.html) {
    return { kind: 'full_page_html', html: obj.html, title: obj.title, seed };
  }
  return null;
}

async function callGroq(env: Env, system: string, user: string, seed: number): Promise<GeneratedPage | null> {
  const models = [
    env.GROQ_MODEL || 'meta-llama/llama-4-scout-17b-16e-instruct',
    env.GROQ_FALLBACK_MODEL || 'qwen/qwen3-32b'
  ].filter(Boolean);

  for (const model of models as string[]) {
    try {
      const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GROQ_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model,
          messages: [
            { role: 'system', content: system },
            { role: 'user', content: user },
          ],
          max_tokens: 8192,
          temperature: 1.2,
          seed,
        }),
      });

      if (!resp.ok) {
        console.error(`Groq error (${model}):`, resp.status, await resp.text());
        continue; // Try next model
      }

      const data = await resp.json() as any;
      const content = data.choices?.[0]?.message?.content;
      const result = parseGeneratedContent(content);
      if (result) return result;
    } catch (err) {
      console.error(`Groq exception (${model}):`, err);
    }
  }
  return null;
}

async function callOpenRouter(env: Env, system: string, user: string, seed: number): Promise<GeneratedPage | null> {
  const models = [
    env.OPENROUTER_MODEL || 'devstral-2512:free',
    env.OPENROUTER_FALLBACK_MODEL_1 || 'google/gemini-2.0-flash-exp:free',
    env.OPENROUTER_FALLBACK_MODEL_2 || 'deepseek/deepseek-chat-v3.1:free'
  ].filter(Boolean);

  for (const model of models as string[]) {
    try {
      const resp = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.OPENROUTER_API_KEY}`,
          'Content-Type': 'application/json',
          'HTTP-Referer': 'https://roulette.example.com',
        },
        body: JSON.stringify({
          model,
          messages: [
            { role: 'system', content: system },
            { role: 'user', content: user },
          ],
          max_tokens: 8192,
          temperature: 1.2,
        }),
      });

      if (!resp.ok) {
        console.error(`OpenRouter error (${model}):`, resp.status, await resp.text());
        continue; // Try next model
      }

      const data = await resp.json() as any;
      const content = data.choices?.[0]?.message?.content;
      const result = parseGeneratedContent(content);
      if (result) return result;
    } catch (err) {
      console.error(`OpenRouter exception (${model}):`, err);
    }
  }
  return null;
}

async function callGemini(env: Env, system: string, user: string, seed: number, imageB64: string | null = null): Promise<GeneratedPage | null> {
  try {
    const model = env.GEMINI_GENERATION_MODEL || 'gemini-1.5-flash';
    const contents: any[] = [
      {
        role: 'user',
        parts: [
          { text: `${system}\n\n${user}` }
        ]
      }
    ];

    if (imageB64) {
      contents[0].parts.push({
        inlineData: {
          mimeType: 'image/jpeg',
          data: imageB64
        }
      });
    }

    const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${env.GEMINI_API_KEY}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents,
        generationConfig: {
          temperature: 1.2,
          maxOutputTokens: 16000,
        },
      }),
    });

    if (!resp.ok) {
      console.error(`Gemini error (${model}):`, resp.status, await resp.text());
      return null;
    }

    const data = await resp.json() as any;
    const content = data.candidates?.[0]?.content?.parts?.[0]?.text;
    return parseGeneratedContent(content);
  } catch (err) {
    console.error('Gemini exception:', err);
    return null;
  }
}

export function parseGeneratedContent(content: string | undefined): GeneratedPage | null {
  if (!content) return null;

  // Try to extract JSON from the content
  let jsonStr = content.trim();
  
  // Remove markdown code fences if present
  const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    jsonStr = jsonMatch[1].trim();
  }

  // Try to find JSON object
  const objMatch = jsonStr.match(/\{[\s\S]*\}/);
  if (objMatch) {
    jsonStr = objMatch[0];
  }

  try {
    const parsed = JSON.parse(jsonStr);
    if (parsed.kind === 'full_page_html' && parsed.html) {
      return parsed as GeneratedPage;
    }
    if (parsed.kind === 'ndw_snippet_v1' && parsed.html) {
      return parsed as GeneratedPage;
    }
    // Try to extract html field even without kind
    if (parsed.html) {
      return { kind: 'full_page_html', html: parsed.html, title: parsed.title, seed: 0 };
    }
  } catch (e) {
    console.error('JSON parse error:', e);
  }

  return null;
}

/**
 * Run a compliance review on the generated page.
 */
export async function maybeRunComplianceReview(env: Env, page: GeneratedPage, brief: string, category: string): Promise<GeneratedPage | null> {
    if (!env.GEMINI_REVIEW_ENABLED) return page;
    
    const results = await runComplianceBatch(env, [page], brief);
    if (results && results.length > 0) {
        const review = results[0];
        if (review.ok === false) {
            console.warn(`[Review] Page rejected: ${JSON.stringify(review.issues)}`);
            return null; // Model rejected it
        }
        return review.doc || page;
    }
    return page;
}

export async function runComplianceBatch(env: Env, pages: GeneratedPage[], brief: string = ''): Promise<any[]> {
    if (!env.GEMINI_API_KEY) return [];
    
    const model = env.GEMINI_REVIEW_MODEL || 'gemini-1.5-flash';
    const instructions = `You are a compliance reviewer and fixer for interactive web apps.
Evaluate each document below. Return a JSON array where each element is:
{"index": <matching APP_INDEX>, "ok": true|false, "issues":[{"severity":"info|warn|block","field":"...","message":"..."}], "doc":{...optional corrected payload...}}
Only set ok=true if the payload (original or corrected) is safe, functional, and accessible.
CRITICAL: Every app MUST have working CSS (internal <style>) and JS (internal <script>).
If it's missing interactivity or looks basic/default, fix it or set ok=false.`;

    const prompt_sections = pages.map((page, idx) => `APP_INDEX: ${idx}\nJSON:\n${JSON.stringify(page)}\n`);
    const prompt = `${instructions}\n\n---\n${prompt_sections.join('\n---\n')}`;

    try {
        const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${env.GEMINI_API_KEY}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: {
                    temperature: 0.0, // Be deterministic for review
                    maxOutputTokens: 16000,
                    responseMimeType: 'application/json',
                }
            })
        });

        if (!resp.ok) {
            console.error(`Gemini Review API error: ${resp.status}`);
            return [];
        }

        const data = await resp.json() as any;
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!text) return [];

        try {
            const results = JSON.parse(text);
            return Array.isArray(results) ? results : (results.results || []);
        } catch (e) {
            // Try to extract if it's wrapped in markdown
            const match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
            if (match) return JSON.parse(match[1]);
            return [];
        }
    } catch (err) {
        console.error('Gemini review exception:', err);
        return [];
    }
}

export function createFallbackHtml(category: string, seed: number): string {
  return `<!doctype html>
<html>
<head>
  <title>Roulette - ${category}</title>
  <style>
    body { margin: 0; padding: 0; min-height: 100vh; background: linear-gradient(to bottom right, #0f172a, #1e293b); display: flex; align-items: center; justify-content: center; font-family: system-ui, -apple-system, sans-serif; color: white; }
    .content { text-align: center; }
    h1 { font-size: 2.25rem; font-weight: 700; margin-bottom: 1rem; }
    p { color: #94a3b8; margin-bottom: 2rem; }
    button { padding: 0.75rem 1.5rem; background: #4f46e5; color: white; border: none; border-radius: 0.5rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
    button:hover { background: #4338ca; }
  </style>
</head>
<body>
  <div class="content">
    <h1>Generation Temporarily Unavailable</h1>
    <p>Please try again in a moment.</p>
    <button onclick="window.ndwGenerate()">
      Try Again
    </button>
  </div>
</body>
</html>`;
}

