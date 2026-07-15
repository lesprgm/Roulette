// NDW runtime is loaded separately; app.ts wires the landing shell to generation and rendering.
import { generateOnce, GenerationHttpError, streamGeneration } from './generation-client.js';
import {
  destroyGeneratedSiteFrame,
  NdwSnippet,
  renderFullPageHost,
  renderSnippetHost,
  showHostError,
} from './generated-site-host.js';
import { LandingController, resolveTunnelCardAction } from './landing-controller.js';

export { };

interface FullPageDoc { kind: 'full_page_html'; html: string }
interface ErrorDoc { error: string }
interface ComponentDoc { components: any[] }
type AppNormalizedDoc = NdwSnippet | FullPageDoc | ErrorDoc | ComponentDoc | any;

type AppWindow = Window & {
  __NDW_showSnippetErrorOverlay?: (err: any) => void;
  API_KEY?: string;
  NDW?: any;
  __ndwEvalRenderDoc?: (doc: AppNormalizedDoc, options?: { hideChrome?: boolean; settleMs?: number }) => Promise<any>;
};
const _w = window as AppWindow;

let mainEl: HTMLElement | null = null;
const QUERY_PARAMS = new URLSearchParams(window.location.search);
const NDW_TEST_MODE = QUERY_PARAMS.has('ndw_test');
const NDW_DEBUG_MODE = QUERY_PARAMS.has('debug') || QUERY_PARAMS.has('ndw_debug');
const NDW_TEST_DEBUG_PREVIEWS = NDW_TEST_MODE && QUERY_PARAMS.has('ndw_test_debug');

function resolveMainEl(): HTMLElement | null {
  if (!mainEl) {
    const el = document.getElementById('appMain');
    if (el) mainEl = el;
  }
  return mainEl;
}

function buildFloatingGenerateMarkup() {
  return `
    <div class="ndw-button button" aria-label="Generate">
      <button id="floatingGenerate" name="checkbox" type="button" aria-label="Generate"></button>
      <span></span><span></span><span></span><span></span>
    </div>
  `;
}

const landingController = new LandingController({
  testMode: NDW_TEST_MODE,
  debugPreviews: NDW_TEST_DEBUG_PREVIEWS,
  onGenerate: event => { void generateNew(event); },
  onLoadPrefetch: id => { void loadPrefetchSite(id); },
  destroyGeneratedSite: destroyGeneratedSiteFrame,
});

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
  if (!NDW_DEBUG_MODE) return;
  if (document.getElementById('jsonOverlay')) return;
  const wrap = document.createElement('div');
  wrap.id = 'jsonOverlay';
  wrap.className = 'fixed top-3 right-3 z-50';
  wrap.innerHTML = `<button id="toggleJsonBtn" type="button" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs">Peek under the hood</button>
  <div id="jsonPanel" class="hidden mt-2 max-w-[60vw] max-h-[60vh] overflow-auto bg-white border border-slate-200 rounded shadow-lg p-3 text-slate-900">
    <pre id="jsonOut" class="text-[11px] whitespace-pre-wrap text-slate-900"></pre>
  </div>`;
  document.body.appendChild(wrap);
  const btn = document.getElementById('toggleJsonBtn') as HTMLButtonElement | null;
  const panel = document.getElementById('jsonPanel');
  if (btn && panel) {
    btn.addEventListener('click', () => {
      panel.classList.toggle('hidden');
      btn.textContent = panel.classList.contains('hidden') ? 'Peek under the hood' : 'Close the hood';
    });
  }
}

export function updateJsonOut(data: any) {
  if (!NDW_DEBUG_MODE) return;
  const jsonOut = document.getElementById('jsonOut');
  if (!jsonOut) return;
  try {
    jsonOut.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    jsonOut.textContent = String(err || 'Failed to stringify JSON');
  }
}

type TransitionKind = 'portal' | 'iris' | 'noise' | 'warp' | 'flash';
const TRANSITIONS: TransitionKind[] = ['portal', 'iris', 'noise', 'warp', 'flash'];
let transitionIndex = 0;
let hasRenderedOnce = false;
let transitionInFlight = false;

function nextTransition(): TransitionKind {
  const t = TRANSITIONS[transitionIndex % TRANSITIONS.length];
  transitionIndex += 1;
  return t;
}

export function __ndwTestResetTransitions() {
  transitionIndex = 0;
  hasRenderedOnce = false;
  transitionInFlight = false;
}

export function __ndwTestSetBodyMode(mode: 'landing' | 'generated') {
  document.body.classList.toggle('landing-mode', mode === 'landing');
  document.body.classList.toggle('generated-mode', mode === 'generated');
}

export function __ndwTestEnsureFloatingGenerate() {
  ensureFloatingGenerate();
}

export async function __ndwTestRenderEvalDoc(
  doc: AppNormalizedDoc,
  options: { hideChrome?: boolean; settleMs?: number } = {},
) {
  if (!NDW_TEST_MODE) {
    throw new Error('Eval render hook is only available in ndw_test mode.');
  }
  if (options.hideChrome === false) {
    document.body.classList.remove('ndw-eval-hide-chrome');
  } else {
    document.body.classList.add('ndw-eval-hide-chrome');
  }
  updateJsonOut(doc);
  landingController.hideHeroOverlay();
  hideLandingElements();
  await enterSite(doc);
  await sleep(Math.max(0, Number(options.settleMs ?? 0)));
  const hero = document.querySelector('.hero-wrap') as HTMLElement | null;
  const heroHidden = !hero || getComputedStyle(hero).display === 'none' || hero.classList.contains('is-hidden');
  return {
    ok: !(doc as any)?.error,
    title: document.title,
    generatedMode: document.body.classList.contains('generated-mode'),
    heroHidden,
  };
}

function installEvalHook() {
  if (!NDW_TEST_MODE) return;
  _w.__ndwEvalRenderDoc = (doc, options) => __ndwTestRenderEvalDoc(doc, options || {});
}

function ensureTransitionStyles() {
  if (document.getElementById('ndw-transition-styles')) return;
  const st = document.createElement('style');
  st.id = 'ndw-transition-styles';
  st.textContent = `
    .ndw-transition-snapshot {
      position: fixed;
      inset: 0;
      width: 100vw;
      height: 100vh;
      pointer-events: none;
      z-index: 9998;
      overflow: hidden;
      transform: translateZ(0);
      will-change: opacity, transform, filter;
    }
    .ndw-transition-overlay {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 9999;
      opacity: 0;
      transform: translateZ(0);
      will-change: opacity, transform, clip-path;
      mix-blend-mode: normal;
    }
    .ndw-transition-noise {
      background-image:
        repeating-linear-gradient(0deg, rgba(255,255,255,0.06) 0, rgba(255,255,255,0.06) 1px, rgba(0,0,0,0.06) 1px, rgba(0,0,0,0.06) 2px),
        repeating-linear-gradient(90deg, rgba(0,0,0,0.05) 0, rgba(0,0,0,0.05) 1px, rgba(255,255,255,0.05) 1px, rgba(255,255,255,0.05) 2px);
    }
  `;
  document.head.appendChild(st);
}

function buildSnapshot(): HTMLElement {
  const snapshot = document.createElement('div');
  snapshot.className = 'ndw-transition-snapshot';
  const bodyStyle = getComputedStyle(document.body);
  snapshot.style.backgroundColor = bodyStyle.backgroundColor;
  snapshot.style.backgroundImage = bodyStyle.backgroundImage;
  snapshot.style.backgroundSize = bodyStyle.backgroundSize;
  snapshot.style.backgroundPosition = bodyStyle.backgroundPosition;
  snapshot.style.backgroundRepeat = bodyStyle.backgroundRepeat;

  const frag = document.createDocumentFragment();
  Array.from(document.body.childNodes).forEach(node => {
    frag.appendChild(node.cloneNode(true));
  });
  snapshot.appendChild(frag);
  snapshot.querySelectorAll('script').forEach(el => el.remove());
  snapshot.querySelectorAll('#floatingGenerateWrap, #jsonOverlay, #sitesCounterFloating, #tunnel-container, .blob-cont, .noise-overlay, #cursor-glow').forEach(el => el.remove());
  snapshot.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
  return snapshot;
}

function getAccentColor(): string {
  try {
    const styles = getComputedStyle(document.body);
    const accent = styles.getPropertyValue('--accent-500').trim();
    if (accent) return accent;
    const primary = styles.getPropertyValue('--primary').trim();
    if (primary) return primary;
    const bg = styles.backgroundColor;
    if (bg && bg !== 'rgba(0, 0, 0, 0)') return bg;
  } catch (_) {
    // ignore
  }
  return '#facc15';
}

function cleanupCurrentWorld() {
  if (_w.NDW?._cleanup) {
    try { _w.NDW._cleanup(); } catch (err) { console.warn('[ndw] cleanup error:', err); }
  }
  document.querySelectorAll('script[data-ndw-world-script="1"]').forEach(el => el.remove());
  document.querySelectorAll('style[data-ndw-sandbox="1"]').forEach(el => el.remove());
  document.getElementById('ndwSnippetError')?.remove();
}

async function runTransition(renderFn: () => void) {
  const target = resolveMainEl();
  if (!target) {
    cleanupCurrentWorld();
    renderFn();
    hasRenderedOnce = true;
    return;
  }
  if (transitionInFlight) {
    cleanupCurrentWorld();
    renderFn();
    return;
  }
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    cleanupCurrentWorld();
    renderFn();
    hasRenderedOnce = true;
    return;
  }
  if (!hasRenderedOnce) {
    cleanupCurrentWorld();
    renderFn();
    hasRenderedOnce = true;
    return;
  }
  ensureTransitionStyles();
  transitionInFlight = true;
  const transition = nextTransition();

  const snapshot = buildSnapshot();
  document.body.appendChild(snapshot);

  const overlay = document.createElement('div');
  overlay.className = 'ndw-transition-overlay';
  document.body.appendChild(overlay);

  const originalOpacity = target.style.opacity;
  const originalTransform = target.style.transform;
  const originalFilter = target.style.filter;
  target.style.opacity = '0';
  target.style.transform = 'scale(1)';
  target.style.filter = 'none';

  try {
    cleanupCurrentWorld();
    renderFn();
  } catch (err) {
    console.error('[ndw] render error during transition', err);
  }

  await new Promise(requestAnimationFrame);

  const animations: Animation[] = [];
  const canAnimate = typeof (snapshot as any).animate === 'function';
  const durations: Record<TransitionKind, number> = {
    portal: 280,
    iris: 260,
    noise: 200,
    warp: 240,
    flash: 160,
  };
  const duration = durations[transition];

  if (canAnimate) {
    const fadeOut = snapshot.animate(
      [
        { opacity: 1, transform: 'scale(1)', filter: 'blur(0px)' },
        { opacity: 0, transform: 'scale(1.01)', filter: 'blur(2px)' },
      ],
      { duration, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'forwards' }
    );
    animations.push(fadeOut);

    const fadeIn = target.animate(
      [
        { opacity: 0, transform: 'scale(0.992)', filter: 'blur(3px)' },
        { opacity: 1, transform: 'scale(1)', filter: 'blur(0px)' },
      ],
      { duration, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'forwards' }
    );
    animations.push(fadeIn);

    if (transition === 'portal') {
      overlay.style.background =
        'radial-gradient(circle at 50% 50%, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.15) 35%, rgba(15,23,42,0) 70%)';
      overlay.style.clipPath = 'circle(0% at 50% 50%)';
      animations.push(
        overlay.animate(
          [
            { opacity: 1, clipPath: 'circle(0% at 50% 50%)' },
            { opacity: 0, clipPath: 'circle(160% at 50% 50%)' },
          ],
          { duration, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', fill: 'forwards' }
        )
      );
    } else if (transition === 'iris') {
      overlay.style.background =
        'radial-gradient(circle at 50% 50%, rgba(15,23,42,0.2) 0%, rgba(15,23,42,0) 60%)';
      animations.push(
        overlay.animate(
          [
            { opacity: 0.6, transform: 'scale(0.75)' },
            { opacity: 0, transform: 'scale(1.4)' },
          ],
          { duration, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'forwards' }
        )
      );
    } else if (transition === 'noise') {
      overlay.classList.add('ndw-transition-noise');
      animations.push(
        overlay.animate(
          [
            { opacity: 0 },
            { opacity: 0.25 },
            { opacity: 0 },
          ],
          { duration: Math.max(180, duration), easing: 'linear', fill: 'forwards' }
        )
      );
    } else if (transition === 'warp') {
      animations.push(
        snapshot.animate(
          [
            { opacity: 1, filter: 'blur(0px)' },
            { opacity: 0, filter: 'blur(6px)' },
          ],
          { duration, easing: 'cubic-bezier(0.25, 0.6, 0.2, 1)', fill: 'forwards' }
        )
      );
      animations.push(
        target.animate(
          [
            { opacity: 0, filter: 'blur(6px)' },
            { opacity: 1, filter: 'blur(0px)' },
          ],
          { duration, easing: 'cubic-bezier(0.25, 0.6, 0.2, 1)', fill: 'forwards' }
        )
      );
    } else if (transition === 'flash') {
      overlay.style.background = getAccentColor();
      animations.push(
        overlay.animate(
          [
            { opacity: 0 },
            { opacity: 0.4 },
            { opacity: 0 },
          ],
          { duration: Math.max(150, duration), easing: 'ease-out', fill: 'forwards' }
        )
      );
    }

    await Promise.all(animations.map(anim => anim.finished.catch(() => {})));
  } else {
    snapshot.style.opacity = '0';
    target.style.opacity = '1';
    await new Promise(resolve => setTimeout(resolve, duration));
  }

  snapshot.remove();
  overlay.remove();
  target.style.opacity = originalOpacity;
  target.style.transform = originalTransform;
  target.style.filter = originalFilter;
  hasRenderedOnce = true;
  transitionInFlight = false;
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
#floatingGenerateWrap{position:fixed !important;left:50% !important;right:auto !important;bottom:24px !important;top:auto !important;transform:translateX(-50%) !important;z-index:9999 !important;width:auto !important;}
body.ndw-eval-hide-chrome #jsonOverlay,
body.ndw-eval-hide-chrome #floatingGenerateWrap,
body.ndw-eval-hide-chrome #sitesCounterFloating,
body.ndw-eval-hide-chrome #landingFallback,
body.ndw-eval-hide-chrome #ndwTestPreviewDock,
body.ndw-eval-hide-chrome .hero-wrap,
body.ndw-eval-hide-chrome #scrollCue{display:none !important;}
`;
  document.head.appendChild(style);
}

let __ndwAppInitialized = false;
export function initApp() {
  if (__ndwAppInitialized) return;
  __ndwAppInitialized = true;
  mainEl = document.getElementById('appMain');
  console.debug('[ndw] app init; readyState=', document.readyState);
  window.addEventListener('message', handleGeneratedFrameMessage);
  ensureControlStyles();
  ensureJsonOverlay();
  installEvalHook();
  landingController.bindPreviewStatusEvents();
  ensureFloatingGenerate();
  landingController.renderLanding();
}

async function enterSite(doc: AppNormalizedDoc) {
  const anyDoc: any = doc;
  if (anyDoc && typeof anyDoc.error === 'string') {
    showError(anyDoc.error);
    return;
  }
  if (anyDoc && anyDoc.kind === 'ndw_snippet_v1') {
    await runTransition(() => renderNdwSnippet(anyDoc as NdwSnippet));
    return;
  }
  if (anyDoc && anyDoc.kind === 'full_page_html' && typeof anyDoc.html === 'string' && anyDoc.html.trim()) {
    await runTransition(() => renderFullPage(anyDoc.html));
    return;
  }
  const comps = Array.isArray(anyDoc?.components) ? anyDoc.components : [];
  const first = comps.find((c: any) => c && c.props && typeof c.props.html === 'string' && c.props.html.trim());
  if (!first) {
    showError('No renderable HTML found');
    return;
  }
  await runTransition(() => renderFullPage(first.props.html));
}

export function renderDocForPreview(doc: AppNormalizedDoc) {
  try {
    document.body.classList.add('generated-mode');
    document.body.classList.remove('landing-mode');
    landingController.removeSitesCounterOverlay();
  } catch (_) {
    // Ignore DOM errors in headless preview mode.
  }
  void enterSite(doc);
}

function setGenerating(is: boolean) {
  const controls = [
    document.getElementById('floatingGenerate'),
    document.getElementById('landingRecoveryBtn'),
    ...Array.from(document.querySelectorAll('[data-gen-button="1"]')),
  ].filter(Boolean) as HTMLElement[];
  controls.forEach(b => {
    if (is) {
      b.setAttribute('aria-busy', 'true');
      b.classList.add('opacity-50', 'pointer-events-none');
    } else {
      b.removeAttribute('aria-busy');
      b.classList.remove('opacity-50', 'pointer-events-none');
    }
  });
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function closeShutter() {
  const shutter = document.getElementById('shutter');
  if (!shutter) return;
  shutter.classList.remove('shutter-open');
  shutter.classList.add('shutter-closed');
  await sleep(650);
}

async function openShutter() {
  const shutter = document.getElementById('shutter');
  if (!shutter) return;
  shutter.classList.remove('shutter-closed');
  shutter.classList.add('shutter-open');
  await sleep(650);
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
  landingController.hideLandingElements();
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
  
  if (mainEl) mainEl.innerHTML = '';
  await closeShutter();

  const panel = document.getElementById('jsonPanel');
  const btn = document.getElementById('toggleJsonBtn');
  if (panel && !panel.classList.contains('hidden')) {
    panel.classList.add('hidden');
    if (btn) btn.textContent = 'Peek under the hood';
  }

  const MIN_DELAY = 3000; // 3s optimistic opening fallback
  const DEADMAN_DELAY = 62000;

  let deadman: any;
  let shutterOpened = false;
  
  // Optimistic Shutter Opening: If 3s pass, ONLY open if we have content ready
  const optimisticTimer = setTimeout(async () => {
    // Only open if we actually have a page rendered (firstPageSeen)
    // If we haven't seen a page yet, we keep the shutter closed so we don't show a blank white screen.
    if ((_w as any).__ndwGenerating && !(_w as any).__ndwTimedOut && firstPageSeen && !shutterOpened) {
      console.debug('[ndw] Optimistic shutter opening triggered (content ready)');
      await openShutter();
      shutterOpened = true;
    }
  }, MIN_DELAY);

  // Lifted to function scope for timer access
  let firstPageSeen = false;

  const renderFirstPage = async (page: any) => {
    clearTimeout(deadman);
    firstPageSeen = true;
    landingController.hideHeroOverlay();
    hideLandingElements();
    hideSpinner();
    updateJsonOut(page);

    const isFullPage = page && page.kind === 'full_page_html' && typeof page.html === 'string' && page.html.trim();

    if (isFullPage) {
      await runTransition(() => renderFullPage(page.html));
    } else {
      await enterSite(page);
    }

    if (!shutterOpened) {
      await openShutter();
      shutterOpened = true;
    }
  };

  const renderFollowupPage = async (page: any) => {
    const isFullPage = page && page.kind === 'full_page_html' && typeof page.html === 'string' && page.html.trim();
    if (isFullPage) {
      await runTransition(() => renderFullPage(page.html));
    } else {
      await enterSite(page);
    }
    updateJsonOut(page);
  };

  const handleEvent = async (event: string, data: any) => {
    if (event === 'page') {
      const page = data;
      if (!firstPageSeen) {
        await renderFirstPage(page);
      } else {
        await renderFollowupPage(page);
      }
    } else if (event === 'error') {
      const errMsg = data?.error || '';
      if (errMsg === 'rate limit exceeded') {
        const waitSecs = data?.retry_after_seconds || 60;
        showError(`Rate limit hit. Try again in ${waitSecs} seconds.`);
      } else if (errMsg === 'model_quota_exhausted') {
        showError('Both AI models are tapped out for the day. Come back tomorrow.');
      } else if (errMsg === 'model_temporarily_unavailable') {
        const waitSecs = data?.retry_after_seconds || 180;
        showError(`The AI is overloaded right now. Try again in about ${waitSecs} seconds.`);
      } else {
        showError('The wheel hit a snag. Give it another spin?');
      }
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
        showError('The wheel spun a little too long. Hit generate again.');
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
    showSpinner();
    startVerbRotator();
    await streamGeneration(seed, signal, handleEvent, petDeadman);
    
    if (!firstPageSeen) {
        // Stream ended but we never saw a page?
        clearTimeout(deadman);
        if (!(_w as any).__ndwTimedOut) {
          showError('The connection flickered. Try once more?');
          if (!shutterOpened) {
            await openShutter();
            shutterOpened = true;
          }
        }
    }

    ensureFloatingGenerate();
  } catch (err) {
    console.error('[ndw] stream error', err);
    if (err instanceof GenerationHttpError && err.status === 429) {
      const waitSecs = err.payload?.retry_after_seconds || 60;
      showError(`Rate limit hit. Try again in ${waitSecs} seconds.`);
      updateJsonOut(err.payload);
      if (!shutterOpened) {
        await openShutter();
        shutterOpened = true;
      }
      return;
    }
    if (!(_w as any).__ndwTimedOut && !firstPageSeen) {
      try {
        await renderFirstPage(await generateOnce(seed));
      } catch (fallbackErr) {
        console.error('[ndw] fallback generate failed', fallbackErr);
        showError('The wheel hit a snag. Give it another spin?');
        if (!shutterOpened) {
          await openShutter();
          shutterOpened = true;
        }
      }
    } else if (!(_w as any).__ndwTimedOut) {
      showError('The wheel hit a snag. Give it another spin?');
      if (!shutterOpened) {
        await openShutter();
        shutterOpened = true;
      }
    }
  } finally {
    if (deadman) clearTimeout(deadman);
    if (optimisticTimer) clearTimeout(optimisticTimer);
    setGenerating(false);
    (_w as any).__ndwGenerating = false;
    activeController = null;
    hideSpinner();
  }
}

function ensureFloatingGenerate() {
  console.debug('[ndw] ensureFloatingGenerate called');
  if (document.body.classList.contains('landing-mode')) {
    const existingWrap = document.getElementById('floatingGenerateWrap');
    if (existingWrap) {
      try { existingWrap.remove(); } catch (_) { }
    }
    return;
  }
  document.getElementById('floatingGenerateWrap')?.remove();
  const generateWrap = document.createElement('div');
  generateWrap.id = 'floatingGenerateWrap';
  generateWrap.innerHTML = buildFloatingGenerateMarkup();
  document.body.appendChild(generateWrap);
  document.getElementById('floatingGenerate')?.addEventListener('click', generateNew);
}

export function __ndwResolveTunnelCardAction(id: string): 'generate' | 'prefetch' {
  return resolveTunnelCardAction(id);
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
    landingController.hideHeroOverlay();
    hideLandingElements();
    updateJsonOut(page);
    
    // Clear tunnel if we are leaving landing (optional, or keep it for back nav)
    // For now we keep it in background but hidden by full page content
    
    await enterSite(page);
    
    // Open shutter
    await openShutter();
    
  } catch (e) {
    console.error('Prefetch load error:', e);
    showError('Failed to load site from queue.');
    await openShutter();
  }
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

function postRenderCommon() {
  ensureFloatingGenerate();
  landingController.removeSitesCounterOverlay();
  ensureScrollableBody();
  try { (window as any).lucide?.createIcons(); } catch (_) { }
}

function handleGeneratedFrameMessage(event: MessageEvent) {
  const data = event.data;
  if (!data || typeof data !== 'object' || data.type !== 'NDW_GENERATE') return;
  void generateNew();
}

function renderFullPage(html: string) {
  try {
    hideLandingElements();
    const target = resolveMainEl();
    if (!target) return;
    renderFullPageHost(target, html);
    postRenderCommon();
  } catch (e) { console.error('Full-page render error:', e); showError('Failed to render content.'); }
}

function renderNdwSnippet(snippet: NdwSnippet) {
  try {
    hideLandingElements();
    const target = resolveMainEl();
    if (!target) return;
    renderSnippetHost(target, snippet);
    postRenderCommon();
  } catch (e) { console.error('NDW snippet render error:', e); showError('Failed to render snippet.'); }
}

function showError(message: string) {
  const target = resolveMainEl();
  if (target) showHostError(target, String(message || 'Error'));
}

function ensureSpinner() {
  let el = document.getElementById('gen-spinner');
  if (!el) { el = document.createElement('div'); el.id = 'gen-spinner'; el.className = 'hidden fixed inset-0 grid place-items-center bg-black/40 z-50'; el.innerHTML = `<div class="flex flex-col items-center gap-3 text-white"><div class="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent"></div><div id="spinnerMsg" class="text-sm">Generating…</div></div>`; document.body.appendChild(el); }
  return el;
}
function showSpinner() { ensureSpinner().classList.remove('hidden'); }
function hideSpinner() { stopVerbRotator(); ensureSpinner().classList.add('hidden'); }

const LOADING_VERBS = [
  "Weaving the canvas…",
  "Rolling the dice…",
  "Spinning the wheel…",
  "Crafting your experience…",
  "Arranging the pieces…",
  "Polishing the pixels…",
  "Staging the scene…",
  "Calibrating controls…",
  "Seeding randomness…",
  "Tuning the motion…",
  "Balancing the palette…",
  "Loading the fonts…",
  "Injecting motion…",
  "Checking contrast…",
  "Running quality checks…",
  "Brewing something new…",
  "Making it weird…",
  "Almost there…",
];

let _verbInterval: ReturnType<typeof setInterval> | null = null;

function startVerbRotator() {
  const msg = document.getElementById('spinnerMsg');
  if (!msg) return;
  let i = Math.floor(Math.random() * LOADING_VERBS.length);
  msg.textContent = LOADING_VERBS[i];
  if (_verbInterval) clearInterval(_verbInterval);
  _verbInterval = setInterval(() => {
    i = (i + 1) % LOADING_VERBS.length;
    msg.textContent = LOADING_VERBS[i];
  }, 3500);
}

function stopVerbRotator() {
  if (_verbInterval) {
    clearInterval(_verbInterval);
    _verbInterval = null;
  }
}
