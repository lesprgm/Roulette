// Migrated TypeScript version of app.js (core client logic)
// NDW runtime is loaded separately via a plain <script src="/static/ts-build/ndw.js"></script>
// I intentionally do NOT import './ndw' so this compiles to a classic script (no type="module").
// Provide an empty export so this file is treated as a module and allows scoped types without polluting global.
export { };

interface NdwBackground { style?: string; class?: string }
interface NdwSnippet { kind: 'ndw_snippet_v1'; title?: string; html?: string; css?: string; js?: string; background?: NdwBackground }
interface FullPageDoc { kind: 'full_page_html'; html: string }
interface ErrorDoc { error: string }
interface ComponentDoc { components: any[] }
type AppNormalizedDoc = NdwSnippet | FullPageDoc | ErrorDoc | ComponentDoc | any;

type AppWindow = Window & {
  __NDW_showSnippetErrorOverlay?: (err: any) => void;
  API_KEY?: string;
  NDW?: any;
};
const _w = window as AppWindow;

const bodyEl = document.body;
let mainEl: HTMLElement | null = null;
const SANDBOX_SCOPE = '#ndw-sandbox';

function resolveMainEl(): HTMLElement | null {
  if (!mainEl) {
    const el = document.getElementById('appMain');
    if (el) mainEl = el;
  }
  return mainEl;
}

function parseRgb(color: string): [number, number, number] {
  const match = color.match(/rgba?\(([^)]+)\)/);
  if (!match) return [255, 255, 255];
  const parts = match[1].split(',').map(part => Number(part.trim()));
  return [parts[0] ?? 255, parts[1] ?? 255, parts[2] ?? 255];
}

function relativeLuminance([r, g, b]: [number, number, number]) {
  const srgb = [r, g, b].map(v => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
}

function ensureReadableTheme(target?: HTMLElement) {
  try {
    const el = target || document.body;
    if (!el.isConnected) return;
    const style = getComputedStyle(el);
    const hasImage = style.backgroundImage && style.backgroundImage !== 'none';
    const bgRgb = parseRgb(style.backgroundColor || 'rgb(255,255,255)');
    const bgLum = relativeLuminance(bgRgb);

    // If background is very light and there's no image, ensure it has a subtle gradient
    if (!hasImage && bgLum > 0.9) {
      el.style.background = 'linear-gradient(140deg,#ffffff,#f1f5f9)';
    }

    const colorRgb = parseRgb(style.color || 'rgb(51,65,85)');
    const colorLum = relativeLuminance(colorRgb);

    // Contrast check: if background and text are both light, or both dark, force high contrast
    if (Math.abs(bgLum - colorLum) < 0.3) {
      if (bgLum > 0.5) {
        // Light background -> Force dark text
        el.style.color = '#1f2937';
      } else {
        // Dark background -> Force light text
        el.style.color = '#f8fafc';
      }
    }
  } catch (err) {
    console.warn('ensureReadableTheme failed', err);
  }
}

function ensureScrollableBody() {
  try {
    document.documentElement.style.overflowX = 'auto';
    document.documentElement.style.overflowY = 'auto';
    document.body.style.overflowX = 'auto';
    document.body.style.overflowY = 'auto';
    document.body.style.removeProperty('overscroll-behavior');
    document.documentElement.style.removeProperty('overscroll-behavior');
    const removable = ['overflow-hidden', 'no-scroll', 'lock-scroll'];
    removable.forEach(cls => {
      if (document.body.classList.contains(cls)) document.body.classList.remove(cls);
      if (document.documentElement.classList.contains(cls)) document.documentElement.classList.remove(cls);
    });
  } catch (err) { console.warn('ensureScrollableBody failed', err); }
}

function ensureJsonOverlay() {
  if (document.getElementById('jsonOverlay')) return;
  const wrap = document.createElement('div');
  wrap.id = 'jsonOverlay';
  wrap.className = 'fixed top-3 right-3 z-50';
  wrap.innerHTML = `<button id="toggleJsonBtn" type="button" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs">Show JSON</button>
  <div id="jsonPanel" class="hidden mt-2 max-w-[60vw] max-h-[60vh] overflow-auto bg-white border border-slate-200 rounded shadow-lg p-3 text-slate-900">
    <pre id="jsonOut" class="text-[11px] whitespace-pre-wrap text-slate-900"></pre>
  </div>`;
  document.body.appendChild(wrap);
  const btn = document.getElementById('toggleJsonBtn') as HTMLButtonElement | null;
  const panel = document.getElementById('jsonPanel');
  if (btn && panel) {
    btn.addEventListener('click', () => {
      panel.classList.toggle('hidden');
      btn.textContent = panel.classList.contains('hidden') ? 'Show JSON' : 'Hide JSON';
    });
  }
}

export function updateJsonOut(data: any) {
  const jsonOut = document.getElementById('jsonOut');
  if (!jsonOut) return;
  try {
    jsonOut.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    jsonOut.textContent = String(err || 'Failed to stringify JSON');
  }
}

function ensureControlStyles() {
  const id = 'ndw-control-style';
  if (document.getElementById(id)) return;
  const style = document.createElement('style');
  style.id = id;
  style.textContent = `
#jsonOverlay{position:fixed;top:12px;right:12px;z-index:10000;display:flex;flex-direction:column;align-items:flex-end;gap:8px;}
#jsonOverlay button{background:rgba(15,23,42,0.92);color:#f8fafc;padding:6px 10px;border-radius:6px;border:1px solid rgba(148,163,184,0.4);font:500 12px/1 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;box-shadow:0 4px 12px rgba(15,23,42,0.35);cursor:pointer;}
#jsonOverlay button:hover{background:rgba(30,41,59,0.95);}
#jsonPanel{background:#ffffff;border:1px solid rgba(148,163,184,0.35);border-radius:10px;box-shadow:0 20px 40px rgba(15,23,42,0.2);}
#floatingGenerateWrap{position:fixed;left:50%;transform:translateX(-50%);bottom:24px;z-index:9999;}
`;
  document.head.appendChild(style);
}

let __ndwAppInitialized = false;
export function initApp() {
  if (__ndwAppInitialized) return;
  __ndwAppInitialized = true;
  mainEl = document.getElementById('appMain');
  console.debug('[ndw] app init; readyState=', document.readyState);
  ensureControlStyles();
  ensureJsonOverlay();
  ensureFloatingGenerate();
  ensureSitesCounterOverlay();
  refreshSitesCounter();
  renderLanding();
}

function scopeCssText(cssText: string, scope: string): string {
  if (!cssText.trim()) return cssText;
  let styleEl: HTMLStyleElement | null = null;
  try {
    styleEl = document.createElement('style');
    styleEl.textContent = cssText;
    document.head.appendChild(styleEl);
    const sheet = styleEl.sheet;
    if (!sheet) return cssText;
    const scoped = processCssRules(Array.from(sheet.cssRules), scope);
    return scoped.join('\n');
  } catch (err) {
    console.warn('scopeCssText failed', err);
    return cssText;
  } finally {
    styleEl?.remove();
  }
}

function processCssRules(rules: CSSRule[], scope: string): string[] {
  const output: string[] = [];
  rules.forEach(rule => {
    switch (rule.type) {
      case CSSRule.STYLE_RULE: {
        const styleRule = rule as CSSStyleRule;
        const selectors = styleRule.selectorText.split(',').map(sel => {
          let trimmed = sel.trim();
          if (!trimmed) return '';
          trimmed = trimmed.replace(/:root/gi, scope);
          trimmed = trimmed.replace(/\bhtml\b/gi, scope);
          trimmed = trimmed.replace(/\bbody\b/gi, scope);
          if (!trimmed.startsWith(scope) && !trimmed.startsWith('@')) {
            trimmed = `${scope} ${trimmed}`;
          }
          return trimmed;
        }).filter(Boolean);
        if (selectors.length) {
          output.push(`${selectors.join(', ')} { ${styleRule.style.cssText} }`);
        }
        break;
      }
      case CSSRule.MEDIA_RULE: {
        const mediaRule = rule as CSSMediaRule;
        const inner = processCssRules(Array.from(mediaRule.cssRules), scope);
        output.push(`@media ${mediaRule.conditionText} { ${inner.join(' ')} }`);
        break;
      }
      case CSSRule.SUPPORTS_RULE: {
        const supportsRule = rule as CSSSupportsRule;
        const inner = processCssRules(Array.from(supportsRule.cssRules), scope);
        output.push(`@supports ${supportsRule.conditionText} { ${inner.join(' ')} }`);
        break;
      }
      case CSSRule.KEYFRAMES_RULE:
      case CSSRule.FONT_FACE_RULE:
      case CSSRule.PAGE_RULE:
      default:
        output.push(rule.cssText);
        break;
    }
  });
  return output;
}

function scopeInlineStyles(container: HTMLElement, scope: string) {
  const styles = Array.from(container.querySelectorAll('style')) as HTMLStyleElement[];
  styles.forEach(styleEl => {
    const scoped = scopeCssText(styleEl.textContent || '', scope);
    styleEl.textContent = scoped;
    styleEl.setAttribute('data-ndw-scoped', '1');
  });
}

const API_KEY = (_w.API_KEY && String(_w.API_KEY)) || (bodyEl.dataset.apiKey && String(bodyEl.dataset.apiKey)) || 'demo_123';

function stripExternalScripts(html: string) {
  return String(html).replace(/<script[^>]*\bsrc\s*=\s*['"][^'"]+['"][^>]*>\s*<\/script>/gi, '');
}

function containsDomReadyHook(code: string): boolean {
  return /DOMContentLoaded/i.test(code);
}

function invokeDomReadyListener(listener: EventListenerOrEventListenerObject): void {
  try {
    const evt = new Event('DOMContentLoaded');
    Object.defineProperty(evt, 'target', { value: document, configurable: true });
    Object.defineProperty(evt, 'currentTarget', { value: document, configurable: true });
    if (typeof listener === 'function') {
      listener.call(document, evt);
    } else if (listener && typeof (listener as any).handleEvent === 'function') {
      (listener as any).handleEvent.call(listener, evt);
    }
  } catch (err) {
    console.warn('ndw dom-ready handler error', err);
  }
}

function ensureOptionalGlobals() {
  const w = window as any;
  if (!w.lucide) {
    w.lucide = { createIcons: () => {} };
  }
  if (!w.gsap) {
    const safeComplete = (vars?: any) => {
      if (vars && typeof vars.onComplete === 'function') {
        try {
          vars.onComplete();
        } catch (err) {
          console.warn('[ndw] gsap stub onComplete error', err);
        }
      }
    };
    const noop = (_target?: any, vars?: any) => {
      safeComplete(vars);
      return {};
    };
    const timeline = (vars?: any) => {
      safeComplete(vars);
      const tl = {
        to: (_target?: any, next?: any) => { safeComplete(next); return tl; },
        from: (_target?: any, next?: any) => { safeComplete(next); return tl; },
        fromTo: (_target?: any, _from?: any, next?: any) => { safeComplete(next); return tl; },
        set: (_target?: any, next?: any) => { safeComplete(next); return tl; },
      };
      return tl;
    };
    w.gsap = {
      to: noop,
      from: noop,
      fromTo: (_target?: any, _from?: any, vars?: any) => { safeComplete(vars); return {}; },
      set: noop,
      timeline,
      quickTo: () => noop,
    };
  }
}

function loadExternalScript(src: string, type?: string | null): Promise<void> {
  return new Promise(resolve => {
    const existing = document.querySelector(`script[src="${src}"]`) as HTMLScriptElement | null;
    const markDone = (el?: HTMLScriptElement) => {
      if (el) {
        el.dataset.ndwLoaded = '1';
      }
      resolve();
    };
    const isReady = () => {
      const w = window as any;
      if (src.includes('gsap') && w.gsap) return true;
      if (src.includes('lucide') && w.lucide) return true;
      if (src.includes('tailwind') && w.tailwind) return true;
      return false;
    };
    if (existing) {
      if (existing.dataset.ndwLoaded === '1' || isReady()) {
        resolve();
        return;
      }
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        existing.dataset.ndwLoaded = '1';
        resolve();
      };
      existing.addEventListener('load', finish, { once: true });
      existing.addEventListener('error', finish, { once: true });
      setTimeout(finish, 4000);
      return;
    }
    const sc = document.createElement('script');
    sc.src = src;
    if (type) sc.type = type;
    sc.async = false;
    sc.addEventListener('load', () => markDone(sc), { once: true });
    sc.addEventListener('error', () => markDone(sc), { once: true });
    document.head.appendChild(sc);
  });
}

function executeDocScripts(scripts: HTMLScriptElement[], target: HTMLElement | null) {
  const externalLoads: Promise<void>[] = [];
  const inlineScripts: HTMLScriptElement[] = [];
  scripts.forEach(old => {
    if (old.src) {
      const src = old.src.toLowerCase();
      const safe =
        src.includes('/static/vendor/') ||
        src.includes('/vendor/') ||
        src.includes('unpkg.com') ||
        src.includes('cdnjs.cloudflare.com/ajax/libs/gsap');
      if (!safe) return;
      externalLoads.push(loadExternalScript(old.src, old.type));
      return;
    }
    inlineScripts.push(old);
  });
  const runInline = () => {
    ensureOptionalGlobals();
    inlineScripts.forEach(old => {
      const code = old.textContent || '';
      const exec = () => {
        const sc = document.createElement('script');
        if (old.type) sc.type = old.type;
        sc.textContent = code;
        try {
          target?.appendChild(sc);
        } catch (err) {
          console.error('[ndw] inline script error', err);
        }
      };
      if (containsDomReadyHook(code)) {
        runWithPatchedDomReady(exec);
      } else {
        exec();
      }
    });
  };
  if (externalLoads.length) {
    Promise.allSettled(externalLoads).then(runInline);
  } else {
    runInline();
  }
}

function runWithPatchedDomReady(exec: () => void): void {
  if (document.readyState === 'loading') {
    exec();
    return;
  }
  const originalAdd = document.addEventListener.bind(document);
  const originalRemove = document.removeEventListener.bind(document);
  const intercepted = new Set<EventListenerOrEventListenerObject>();
  function patchedAdd(
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: boolean | AddEventListenerOptions,
  ): void {
    if (type === 'DOMContentLoaded' && listener) {
      intercepted.add(listener);
      invokeDomReadyListener(listener);
      return;
    }
    originalAdd(type, listener as EventListenerOrEventListenerObject, options as any);
  }
  function patchedRemove(
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: boolean | EventListenerOptions,
  ): void {
    if (type === 'DOMContentLoaded' && listener) {
      intercepted.delete(listener);
      return;
    }
    originalRemove(type, listener as EventListenerOrEventListenerObject, options as any);
  }
  document.addEventListener = patchedAdd as typeof document.addEventListener;
  document.removeEventListener = patchedRemove as typeof document.removeEventListener;
  try {
    exec();
  } finally {
    document.addEventListener = originalAdd;
    document.removeEventListener = originalRemove;
    intercepted.clear();
  }
}

function enterSite(doc: AppNormalizedDoc) {
  const anyDoc: any = doc;
  if (anyDoc && typeof anyDoc.error === 'string') return showError(anyDoc.error);
  if (anyDoc && anyDoc.kind === 'ndw_snippet_v1') return renderNdwSnippet(anyDoc as NdwSnippet);
  if (anyDoc && anyDoc.kind === 'full_page_html' && typeof anyDoc.html === 'string' && anyDoc.html.trim()) return renderFullPage(anyDoc.html);
  const comps = Array.isArray(anyDoc?.components) ? anyDoc.components : [];
  const first = comps.find((c: any) => c && c.props && typeof c.props.html === 'string' && c.props.html.trim());
  if (!first) return showError('No renderable HTML found');
  renderInline(first.props.html);
}

export function renderDocForPreview(doc: AppNormalizedDoc) {
  try {
    document.body.classList.add('generated-mode');
    document.body.classList.remove('landing-mode');
  } catch (_) {
    // Ignore DOM errors in headless preview mode.
  }
  enterSite(doc);
}

async function callGenerate(brief: string, seed: number) {
  const resp = await fetch('/generate', { method: 'POST', headers: { 'content-type': 'application/json', 'x-api-key': API_KEY }, body: JSON.stringify({ brief, seed }) });
  if (!resp.ok) {
    const text = await resp.text();
    return { error: `Generate failed (${resp.status}): ${text || resp.statusText}` };
  }
  return resp.json();
}

function setGenerating(is: boolean) {
  const coreBtns = [document.getElementById('landingGenerate'), document.getElementById('floatingGenerate')].filter(Boolean) as HTMLElement[];
  const inlineBtns = Array.from(document.querySelectorAll('[data-gen-button="1"]')) as HTMLElement[];
  [...coreBtns, ...inlineBtns].forEach(b => {
    if (is) {
      b.setAttribute('aria-busy', 'true');
      b.classList.add('opacity-50', 'pointer-events-none');
    } else {
      b.removeAttribute('aria-busy');
      b.classList.remove('opacity-50', 'pointer-events-none');
    }
  });
}

async function closeShutter() {
  return;
}

async function openShutter() {
  return;
}

// Progressive Reveal: feature is fully disabled (kept as no-op for compatibility).
export async function prepareReveal() {
  const mainEl = document.getElementById('appMain');
  if (!mainEl) return;
  mainEl.style.opacity = '1';
}

export async function playReveal() {
  const mainEl = document.getElementById('appMain');
  if (!mainEl) return;
  mainEl.style.opacity = '1';
}

export function hideLandingElements() {
    const selectors = ['.blob-cont', '.noise-overlay', '#cursor-glow'];
    selectors.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) el.remove();
    });
    const tunnelContainer = document.getElementById('tunnel-container');
    if (tunnelContainer) tunnelContainer.style.display = 'none';
    if (tunnel) {
      tunnel.destroy();
      tunnel = null;
    }
    document.body.classList.add('generated-mode');
    document.body.classList.remove('landing-mode');
    document.body.style.removeProperty('min-height');
    document.body.style.removeProperty('background');
    document.body.style.removeProperty('background-image');
    document.body.style.removeProperty('background-color');
    document.documentElement.style.removeProperty('min-height');
}

function setupLandingCues() {
  if ((_w as any).__ndwLandingCues) return;
  const hint = document.getElementById('heroHint');
  const cue = document.getElementById('scrollCue');
  if (!hint && !cue) return;
  (_w as any).__ndwLandingCues = true;

  let hintTimer: number | undefined;
  let cueTimer: number | undefined;

  const hideAll = () => {
    if (hintTimer) window.clearTimeout(hintTimer);
    if (cueTimer) window.clearTimeout(cueTimer);
    hint?.classList.add('is-hidden');
    cue?.classList.add('is-hidden');
    window.removeEventListener('scroll', onScroll);
  };

  const onScroll = () => {
    if (window.scrollY > 24) {
      hideAll();
    }
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  hintTimer = window.setTimeout(() => hint?.classList.add('is-hidden'), 4500);
  cueTimer = window.setTimeout(() => cue?.classList.add('is-hidden'), 5500);
}

// export function _resetMainEl() {
//   mainEl = document.getElementById('appMain');
//   // console.error('[debug] _resetMainEl found:', mainEl?.id);
// }

let activeController: AbortController | null = null;

(_w as any).ndwGenerate = generateNew;
async function generateNew(e?: Event) {
  if ((_w as any).__ndwGenerating) {
    console.debug('[ndw] generation already in progress, ignoring click');
    return;
  }
  
  if (activeController) {
    activeController.abort();
    activeController = null;
  }
  
  activeController = new AbortController();
  const signal = activeController.signal;

  console.debug('[ndw] generateNew invoked (streaming burst)');
  if (e) e.preventDefault();
  const seed = Math.floor(Math.random() * 1e9);
  const jsonOut = document.getElementById('jsonOut');
  if (jsonOut) jsonOut.textContent = '';

  (_w as any).__ndwGenerating = true;
  (_w as any).__ndwTimedOut = false;
  setGenerating(true);
  
  // Cleanup previous site's resources before rendering new content
  if (_w.NDW?._cleanup) {
    try { _w.NDW._cleanup(); } catch (e) { console.warn('[ndw] cleanup error:', e); }
  }
  
  if (mainEl) mainEl.innerHTML = '';
  await closeShutter();

  const panel = document.getElementById('jsonPanel');
  const btn = document.getElementById('toggleJsonBtn');
  if (panel && !panel.classList.contains('hidden')) {
    panel.classList.add('hidden');
    if (btn) btn.textContent = 'Show JSON';
  }

  const startTime = Date.now();
  const MIN_DELAY = 3000; // 3s optimistic opening fallback
  const PATIENCE_DELAY = 5000; // 5s: Update spinner text
  const DEADMAN_DELAY = 80000; // 80s: Give up

  let deadman: any;
  let optimisticTimer: any;
  let patienceTimer: any;
  let shutterOpened = false;
  
  // Optimistic Shutter Opening: If 3s pass, ONLY open if we have content ready
  optimisticTimer = setTimeout(async () => {
    // Only open if we actually have a page rendered (firstPageSeen)
    // If we haven't seen a page yet, we keep the shutter closed so we don't show a blank white screen.
    if ((_w as any).__ndwGenerating && !(_w as any).__ndwTimedOut && firstPageSeen && !shutterOpened) {
      console.debug('[ndw] Optimistic shutter opening triggered (content ready)');
      await openShutter();
      shutterOpened = true;
    }
  }, MIN_DELAY);

  // Patience Timer: If 5s pass and still nothing, reassure the user
  patienceTimer = setTimeout(() => {
    if ((_w as any).__ndwGenerating && !firstPageSeen) {
       showSpinner('Connecting to deep logic…');
    }
  }, PATIENCE_DELAY);

  // Lifted to function scope for timer access
  let firstPageSeen = false;

  const renderFirstPage = async (page: any) => {
    clearTimeout(deadman);
    firstPageSeen = true;
    hideHeroOverlay();
    hideLandingElements();
    hideSpinner();
    updateJsonOut(page);

    const isFullPage = page && page.kind === 'full_page_html' && typeof page.html === 'string' && page.html.trim();

    if (isFullPage) {
      // Double-Buffering: Render to hidden buffer first
      const buffer = document.getElementById('ndw-sandbox-buffer');
      if (buffer) {
        renderToTarget(page.html, buffer);
        // Swap buffer to main
        const target = resolveMainEl();
        if (target) {
          target.innerHTML = '';
          target.appendChild(buffer.firstElementChild?.cloneNode(true) || document.createTextNode(''));
        }
      } else {
        renderFullPage(page.html);
      }
    } else {
      enterSite(page);
    }

    if (!shutterOpened) {
      await openShutter();
      shutterOpened = true;
    }
  };

  const renderFollowupPage = (page: any) => {
    const isFullPage = page && page.kind === 'full_page_html' && typeof page.html === 'string' && page.html.trim();
    if (isFullPage) {
      renderFullPage(page.html);
    } else {
      enterSite(page);
    }
    updateJsonOut(page);
  };

  const handleEvent = async (event: string, data: any) => {
    if (event === 'page') {
      const page = data;
      if (!firstPageSeen) {
        await renderFirstPage(page);
      } else {
        renderFollowupPage(page);
      }
    } else if (event === 'error') {
      showError(`Generation error: ${data.error}`);
      updateJsonOut(data);
      hideSpinner();
      if (!shutterOpened) {
        await openShutter();
        shutterOpened = true;
      }
    }
  };

  const petDeadman = () => {
    if (deadman) clearTimeout(deadman);
    deadman = setTimeout(() => {
      if (!firstPageSeen) {
        console.error('[ndw] Shutter deadman triggered');
        (_w as any).__ndwTimedOut = true;
        showError('Generation timed out. Please try again.');
        if (!shutterOpened) {
          openShutter();
          shutterOpened = true;
        }
        setGenerating(false);
        hideSpinner();
      }
    }, DEADMAN_DELAY); 
  };

  try {
    const resp = await fetch('/generate/stream', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': API_KEY },
      body: JSON.stringify({ brief: '', seed }),
      signal
    });

    if (!resp.ok) throw new Error(`Stream failed: ${resp.status}`);
    const reader = resp.body?.getReader();
    if (!reader) throw new Error('No reader');

    const decoder = new TextDecoder();
    let messageBuffer = '';
    let currentEvent = '';

    petDeadman();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      petDeadman(); 
      messageBuffer += decoder.decode(value, { stream: true });
      const lines = messageBuffer.split('\n');
      messageBuffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        
        if (trimmed.startsWith('event: ')) {
          currentEvent = trimmed.substring(7);
        } else if (trimmed.startsWith('data: ')) {
          const dataStr = trimmed.substring(6);
          try {
            const data = JSON.parse(dataStr);
            await handleEvent(currentEvent, data);
          } catch (e) {
            console.warn('SSE parse error', e);
          }
        } else if (trimmed.startsWith('{')) {
          try {
            const payload = JSON.parse(trimmed);
            const event = payload?.event || '';
            const data = payload?.data ?? payload;
            if (event) {
              await handleEvent(event, data);
            }
          } catch (e) {
            console.warn('NDJSON parse error', e);
          }
        }
      }
    }
    
    if (!firstPageSeen) {
        // Stream ended but we never saw a page?
        clearTimeout(deadman);
        if (!(_w as any).__ndwTimedOut) {
          showError('Connection closed before content was ready. Try again?');
          if (!shutterOpened) {
            await openShutter();
            shutterOpened = true;
          }
        }
    }

    ensureFloatingGenerate();
    adaptGenerateButtons();
  } catch (err) {
    console.error('[ndw] stream error', err);
    if (!(_w as any).__ndwTimedOut && !firstPageSeen) {
      try {
        const fallback = await callGenerate('', seed);
        if (fallback && !fallback.error) {
          await renderFirstPage(fallback);
        } else {
          showError(fallback?.error || 'Generation failed. Please try again.');
          if (!shutterOpened) {
            await openShutter();
            shutterOpened = true;
          }
        }
      } catch (fallbackErr) {
        console.error('[ndw] fallback generate failed', fallbackErr);
        showError('Generation failed. Please try again.');
        if (!shutterOpened) {
          await openShutter();
          shutterOpened = true;
        }
      }
    } else if (!(_w as any).__ndwTimedOut) {
      showError('Generation failed. Please try again.');
      if (!shutterOpened) {
        await openShutter();
        shutterOpened = true;
      }
    }
  } finally {
    if (deadman) clearTimeout(deadman);
    if (optimisticTimer) clearTimeout(optimisticTimer);
    if (patienceTimer) clearTimeout(patienceTimer);
    setGenerating(false);
    (_w as any).__ndwGenerating = false;
    activeController = null;
    hideSpinner();
  }
}

// Utility to render content to a specific target element
function renderToTarget(html: string, target: HTMLElement) {
    const doc = parseHtmlDocument(html);
    applyGeneratedStyles(doc, false);
    populateTargetFromDoc(doc, target);
    executeScriptsFromDoc(doc, target);
}

function ensureFloatingGenerate() {
  console.debug('[ndw] ensureFloatingGenerate called');
  const existing = document.getElementById('floatingGenerateWrap');
  if (existing) existing.remove(); else {
    const oldBtn = document.getElementById('floatingGenerate');
    if (oldBtn) { const parent = oldBtn.closest('#floatingGenerateWrap') || oldBtn.parentElement || oldBtn; try { parent.remove(); } catch (_) { } }
  }
  const wrap = document.createElement('div');
  wrap.id = 'floatingGenerateWrap'; wrap.className = 'fixed left-1/2 -translate-x-1/2 bottom-6 z-50';
  wrap.innerHTML = `<div class="ndw-button button" aria-label="Generate"><button id="floatingGenerate" name="checkbox" type="button" aria-label="Generate"></button><span></span><span></span><span></span><span></span></div>`;
  document.body.appendChild(wrap);
  document.getElementById('floatingGenerate')?.addEventListener('click', generateNew);
}

import { InfiniteTunnel } from './tunnel.js';

// ... existing code ...

let tunnel: InfiniteTunnel | null = null;

async function initTunnel() {
  const container = document.getElementById('tunnel-container');
  if (container && !tunnel) {
    tunnel = new InfiniteTunnel(container);
    tunnel.setOnCardClick((id) => loadPrefetchSite(id));
    await tunnel.init();
    tunnel.setTheme(false); // Default to light mode for tunnel
  }
}

async function loadPrefetchSite(id: string) {
  if ((_w as any).__ndwGenerating) return;
  console.debug(`[ndw] loading queued site ${id}`);
  
  // Close shutter to transition
  await closeShutter();
  
  try {
    const resp = await fetch(`/api/prefetch/${encodeURIComponent(id)}`);
    if (!resp.ok) throw new Error(`Prefetch load failed: ${resp.status}`);
    const page = await resp.json();
    hideHeroOverlay();
    hideLandingElements();
    updateJsonOut(page);
    
    // Clear tunnel if we are leaving landing (optional, or keep it for back nav)
    // For now we keep it in background but hidden by full page content
    
    enterSite(page);
    
    // Open shutter
    await openShutter();
    
  } catch (e) {
    console.error('Prefetch load error:', e);
    showError('Failed to load site from queue.');
    await openShutter();
  }
}

function lockHeroOverlay() {
  const hero = document.querySelector('.hero-wrap') as HTMLElement | null;
  if (!hero) return;
  if (hero.parentElement !== document.body) {
    document.body.appendChild(hero);
  }
  hero.style.position = 'fixed';
  hero.style.top = '0';
  hero.style.left = '0';
  hero.style.width = '100%';
  hero.style.height = '100vh';
  hero.style.zIndex = '10';
  hero.style.pointerEvents = 'none';
  hero.style.display = 'flex';
  hero.style.flexDirection = 'column';
  hero.style.justifyContent = 'center';
  hero.style.alignItems = 'center';
  hero.style.textAlign = 'center';
  hero.style.transform = 'translateZ(0)';
  hero.style.willChange = 'transform';
  const container = hero.querySelector('.container') as HTMLElement | null;
  if (container) {
    container.style.pointerEvents = 'auto';
  }
}

function hideHeroOverlay() {
  const hero = document.querySelector('.hero-wrap') as HTMLElement | null;
  if (!hero) return;
  hero.classList.add('is-hidden');
  document.body.classList.remove('landing-mode');
  document.body.classList.add('generated-mode');
}

function showHeroOverlay() {
  const hero = document.querySelector('.hero-wrap') as HTMLElement | null;
  if (!hero) return;
  hero.classList.remove('is-hidden');
  document.body.classList.add('landing-mode');
  document.body.classList.remove('generated-mode');
}

function renderLanding() {
  const btn = document.getElementById('landingGenerate');
  if (btn && !(btn as any).__ndwBound) {
    btn.addEventListener('click', generateNew);
    (btn as any).__ndwBound = true;
    console.debug('[ndw] landingGenerate bound');
  }
  
  // Initialize 3D Tunnel
  initTunnel().catch(e => console.error('[ndw] Tunnel init failed', e));
  lockHeroOverlay();
  showHeroOverlay();
  setupLandingCues();
}

function ensureSitesCounterOverlay() {
  if (document.getElementById('sitesCounterFloating')) return;
  const wrap = document.createElement('div');
  wrap.id = 'sitesCounterFloating'; wrap.className = 'fixed right-3 top-16 z-50';
  wrap.innerHTML = `<div id="sitesCounterBadge" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs shadow border border-slate-700/50">Sites generated: 0</div>`;
  document.body.appendChild(wrap);
}

async function refreshSitesCounter() {
  try {
    const el = document.getElementById('sitesCounter');
    const badge = document.getElementById('sitesCounterBadge');
    const resp = await fetch('/metrics/total', { headers: { accept: 'application/json' } });
    if (!resp.ok) throw new Error(String(resp.status));
    const data = await resp.json();
    const n = typeof data?.total === 'number' ? data.total : 0;
    if (el) el.textContent = `Sites generated: ${n}`;
    if (badge) badge.textContent = `Sites generated: ${n}`;
  } catch { }
}
function autoInitIfEnabled() {
  if ((_w as any).__ndwDisableAutoInit) return;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
}
autoInitIfEnabled();

// Update browser tab title without showing an on-page overlay.
function upsertTitleOverlay(title?: string) {
  const existing = document.getElementById('ndw-title');
  if (existing && existing.parentNode) {
    existing.parentNode.removeChild(existing);
  }
  if (typeof title === 'string' && title.trim()) {
    document.title = title.trim();
  }
}

function escapeHtml(s: string) { return s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'); }

function parseHtmlDocument(html: string): Document {
  const parser = new DOMParser();
  return parser.parseFromString(String(html), 'text/html');
}

function applyGeneratedStyles(doc: Document, clearExisting: boolean) {
  if (clearExisting) {
    document.querySelectorAll('style[data-gen-style="1"]').forEach(s => s.remove());
  }
  doc.head?.querySelectorAll('style').forEach(s => {
    const st = document.createElement('style');
    st.setAttribute('data-gen-style', '1');
    const typeAttr = s.getAttribute('type');
    if (typeAttr) st.setAttribute('type', typeAttr);
    st.textContent = s.textContent || '';
    document.head.appendChild(st);
  });
}

function populateTargetFromDoc(doc: Document, target: HTMLElement | null) {
  if (!target) return;
  target.innerHTML = '';
  const frag = document.createDocumentFragment();
  const nodes = doc.body ? Array.from(doc.body.childNodes) : [];
  nodes.forEach(n => frag.appendChild(n.cloneNode(true)));
  target.appendChild(frag);
}

function executeScriptsFromDoc(doc: Document, target: HTMLElement | null) {
  const scripts: HTMLScriptElement[] = [];
  if (doc.head) scripts.push(...Array.from(doc.head.querySelectorAll('script')));
  if (doc.body) scripts.push(...Array.from(doc.body.querySelectorAll('script')));
  executeDocScripts(scripts, target);
}

function postRenderCommon(options?: { skipReadable?: boolean }) {
  ensureFloatingGenerate();
  ensureSitesCounterOverlay();
  adaptGenerateButtons();
  ensureScrollableBody();
  upsertTitleOverlay(undefined);
  const skipReadable = options?.skipReadable ?? document.body.classList.contains('generated-mode');
  if (!skipReadable) ensureReadableTheme();
  try { (window as any).lucide?.createIcons(); } catch (_) { }
}

function renderFullPage(html: string) {
  try {
    const doc = parseHtmlDocument(html);
    applyGeneratedStyles(doc, true);
    document.body.style.cssText = '';
    // Do NOT wipe document.body.className completely to protect host classes like ndw-base
    const hostClasses = ['ndw-base', 'generated-mode'];
    const currentClasses = Array.from(document.body.classList);
    const toKeep = currentClasses.filter(c => hostClasses.includes(c));
    document.body.className = toKeep.join(' ');
    
    hideLandingElements();

    if (doc.body) {
      const newStyle = doc.body.getAttribute('style');
      const newClass = doc.body.getAttribute('class');
      if (newStyle) document.body.style.cssText = newStyle;
      if (newClass) {
        newClass.split(/\s+/).forEach(c => {
          const next = c.trim();
          if (!next || next === 'landing-mode') return;
          document.body.classList.add(next);
        });
      }
    }
    document.body.classList.remove('landing-mode');
    const target = resolveMainEl();
    populateTargetFromDoc(doc, target);
    executeScriptsFromDoc(doc, target);
    postRenderCommon({ skipReadable: true });
  } catch (e) { console.error('Full-page render error:', e); showError('Failed to render content.'); }
}

function renderInline(html: string) {
  try {
    const doc = parseHtmlDocument(html);
    applyGeneratedStyles(doc, false);
    const target = resolveMainEl();
    populateTargetFromDoc(doc, target);
    executeScriptsFromDoc(doc, target);
    postRenderCommon();
  } catch (e) { console.error('Inline render error:', e); showError('Failed to render content.'); }
}

function renderNdwSnippet(snippet: NdwSnippet) {
  try {
    const bg = snippet.background || {};
    const hasBg = (typeof bg.style === 'string' && bg.style.trim()) || (typeof bg.class === 'string' && bg.class.trim());
    document.querySelectorAll('style[data-ndw-sandbox="1"]').forEach(s => s.remove());
    const target = resolveMainEl();
    if (target) {
      target.innerHTML = '';
      const sandbox = document.createElement('div');
      sandbox.id = 'ndw-sandbox';
      sandbox.className = 'ndw-sandbox';
      sandbox.style.position = 'relative';
      sandbox.style.minHeight = '60vh';
      sandbox.style.padding = '24px';
      sandbox.style.background = 'linear-gradient(135deg,#f1f5f9,#e2e8f0)';
      sandbox.style.color = '#0f172a';
      if (hasBg) {
        if (bg.style) { sandbox.setAttribute('style', `${sandbox.getAttribute('style') || ''}; ${bg.style}`.trim()); }
        if (bg.class) { sandbox.className = `${sandbox.className} ${bg.class}`.trim(); }
      }
      const appRoot = document.createElement('div');
      appRoot.id = 'ndw-app';
      sandbox.appendChild(appRoot);
      const html = snippet.html || '';
      const safeHtml = html; // executeDocScripts will handle whitelisting
      const hasCanvasCreation = /NDW\.makeCanvas/.test(snippet.js || '');
      if (safeHtml.trim()) {
        appRoot.innerHTML = safeHtml;
        // Also extract and run any scripts found in the HTML
        const parser = new DOMParser();
        const doc = parser.parseFromString(safeHtml, 'text/html');
        const embedded = Array.from(doc.querySelectorAll('script'));
        executeDocScripts(embedded, appRoot);
        const nested = appRoot.querySelector('#ndw-app');
        if (nested && nested !== appRoot) {
          const cls = nested.getAttribute('class');
          const sty = nested.getAttribute('style');
          if (cls) appRoot.className = `${appRoot.className} ${cls}`.trim();
          if (sty) appRoot.setAttribute('style', `${appRoot.getAttribute('style') || ''}; ${sty}`.trim());
          const kids = Array.from(nested.childNodes);
          nested.remove();
          kids.forEach(n => appRoot.appendChild(n));
        }
      } else if (!hasCanvasCreation) {
        const c = document.createElement('canvas');
        c.id = 'canvas';
        c.style.display = 'block';
        c.style.width = '100%';
        c.style.minHeight = '60vh';
        appRoot.appendChild(c);
      }
      target.appendChild(sandbox);
      scopeInlineStyles(sandbox, SANDBOX_SCOPE);
      ensureReadableTheme(sandbox);
    }
    upsertTitleOverlay(snippet.title);
    ensureControlStyles();
    if (snippet.css && snippet.css.trim()) {
      const scopedCss = scopeCssText(snippet.css, SANDBOX_SCOPE);
      const st = document.createElement('style');
      st.setAttribute('data-ndw-sandbox', '1');
      st.textContent = scopedCss;
      document.head.appendChild(st);
    }
    if (snippet.js && snippet.js.trim()) {
      if (!_w.NDW) console.warn('NDW runtime not found; snippet JS may fail.');
      if (!_w.__NDW_showSnippetErrorOverlay) {
        _w.__NDW_showSnippetErrorOverlay = (err: any) => {
          try { let el = document.getElementById('ndwSnippetError'); if (!el) { el = document.createElement('div'); el.id = 'ndwSnippetError'; Object.assign(el.style, { position: 'fixed', top: '12px', left: '12px', zIndex: '1000', background: 'rgba(220,38,38,0.95)', color: '#fff', padding: '10px 12px', borderRadius: '8px', font: '12px/1.4 system-ui, sans-serif', boxShadow: '0 6px 20px rgba(0,0,0,0.25)', maxWidth: '60vw' }); el.innerHTML = '<strong>Snippet error</strong><div id="ndwSnippetErrorMsg" style="margin-top:6px;white-space:pre-wrap"></div>'; document.body.appendChild(el); } const msg = document.getElementById('ndwSnippetErrorMsg'); if (msg) msg.textContent = String(err && (err.message || err)).slice(0, 500); } catch (e) { console.error('Snippet error overlay failure', e); }
        };
      }
      const rawJs = snippet.js;
      
      // Security: Basic Keyword Stripping (Tier 1.5 Runtime Check)
      // This prevents obvious malicious network/eval calls in the generated snippet
      const dangerous = /\b(fetch|XMLHttpRequest|WebSocket|Worker|eval|Function|import)\b/g;
      if (dangerous.test(rawJs || '')) {
         console.warn('[ndw] Blocked dangerous API in snippet JS');
         showError('Security Block: Dangerous API usage detected.');
         return;
      }

      const execSnippet = () => {
        const sc = document.createElement('script'); sc.type = 'text/javascript';
        sc.textContent = `(function(){try
{${rawJs}
}catch(err){try{(window.__NDW_showSnippetErrorOverlay||console.error).call(window,err);}catch(_){console.error(err);}}})();`;
        document.body.appendChild(sc);
      };
      if (rawJs && containsDomReadyHook(rawJs)) {
        runWithPatchedDomReady(execSnippet);
      } else {
        execSnippet();
      }
    }
    postRenderCommon();
    const sandboxEl = document.getElementById('ndw-sandbox');
    if (sandboxEl instanceof HTMLElement) ensureReadableTheme(sandboxEl);
  } catch (e) { console.error('NDW snippet render error:', e); showError('Failed to render snippet.'); }
}


function showError(msg: string) { const target = resolveMainEl(); if (!target) return; const wrap = document.createElement('div'); wrap.className = 'max-w-xl mx-auto mt-8 px-4'; wrap.innerHTML = `<div class="p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">${escapeHtml(String(msg || 'Error'))}</div>`; target.innerHTML = ''; target.appendChild(wrap); }

let __genBtnSeq = 0;
function buildUiverseButton(id?: string) { const wrap = document.createElement('div'); wrap.className = 'inline-block align-middle'; wrap.innerHTML = `<div class="ndw-button button" aria-label="Generate"><button ${id ? `id="${id}"` : ''} data-gen-button="1" name="checkbox" type="button" aria-label="Generate"></button><span></span><span></span><span></span><span></span></div>`; return wrap; }

function looksLikeGenerate(el: HTMLElement) {
  const datasetTrigger = (el.dataset?.ndwTrigger || '').toLowerCase();
  if (datasetTrigger === 'new-site' || datasetTrigger === 'generate') return true;
  if (el.dataset?.ndwNoHijack === '1') return false;
  const label = (el.getAttribute('aria-label') || el.textContent || '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
  const id = (el.id || '').trim().toLowerCase();
  const cls = (el.className || '').toLowerCase();
  if (id === 'landinggenerate' || id === 'floatinggenerate') return false;
  if (el.closest('.button')) return false;
  const explicitLabels = new Set(['generate', 'generate website', 'generate a website', 'new site', 'new website']);
  if (explicitLabels.has(label)) return true;
  const explicitIds = new Set(['generate', 'generate-website', 'generatewebsite', 'ndw-generate', 'new-site']);
  if (explicitIds.has(id)) return true;
  if (/\bndw-(?:global-)?generate\b/.test(cls)) return true;
  return false;
}

function adaptGenerateButtons() {
  const scope = mainEl || document;
  const candidates = Array.from(scope.querySelectorAll('button, a[role="button"], a[href="#generate"], input[type="button"], input[type="submit"]')) as HTMLElement[];
  candidates.forEach(el => {
    if (!looksLikeGenerate(el)) return;
    const newId = `inlineGenerate_${++__genBtnSeq}`;
    const comp = buildUiverseButton(newId);
    comp.style.display = getComputedStyle(el).display === 'block' ? 'block' : 'inline-block';
    el.replaceWith(comp);
    const btn = comp.querySelector('button');
    btn?.addEventListener('click', generateNew);
  });
}

function ensureSpinner() {
  let el = document.getElementById('gen-spinner');
  if (!el) { el = document.createElement('div'); el.id = 'gen-spinner'; el.className = 'hidden fixed inset-0 grid place-items-center bg-black/40 z-50'; el.innerHTML = `<div class="flex flex-col items-center gap-3 text-white"><div class="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent"></div><div id="spinnerMsg" class="text-sm">Generating…</div></div>`; document.body.appendChild(el); }
  return el;
}
function showSpinner(msg?: string) { const el = ensureSpinner(); const m = document.getElementById('spinnerMsg'); if (m && msg) m.textContent = msg; el.classList.remove('hidden'); }
function hideSpinner() { ensureSpinner().classList.add('hidden'); }

const _origEnterSite = enterSite;
function enterSiteWithCounter(doc: any) { _origEnterSite(doc); if (doc && !doc.error) refreshSitesCounter(); }
// @ts-ignore
enterSite = enterSiteWithCounter;
