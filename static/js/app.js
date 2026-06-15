// Migrated TypeScript version of app.js (core client logic)
// NDW runtime is loaded separately; app.ts owns the host shell and iframe lifecycle.
import { buildGeneratedFrame, extractDocumentTitle } from './frame_renderer.js';
const _w = window;
const bodyEl = document.body;
let mainEl = null;
let activeSiteFrame = null;
const SANDBOX_SCOPE = '#ndw-sandbox';
const QUERY_PARAMS = new URLSearchParams(window.location.search);
const NDW_TEST_MODE = QUERY_PARAMS.has('ndw_test');
const NDW_TEST_DEBUG_PREVIEWS = NDW_TEST_MODE && QUERY_PARAMS.has('ndw_test_debug');
let previewStatusBound = false;
function resolveMainEl() {
    if (!mainEl) {
        const el = document.getElementById('appMain');
        if (el)
            mainEl = el;
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
function setLandingFallbackVisible(visible) {
    const fallback = document.getElementById('landingFallback');
    if (!fallback)
        return;
    fallback.hidden = !visible;
    fallback.setAttribute('aria-hidden', visible ? 'false' : 'true');
}
function renderTestPreviewDock(previews) {
    const dock = document.getElementById('ndwTestPreviewDock');
    if (!dock)
        return;
    if (!NDW_TEST_DEBUG_PREVIEWS) {
        dock.hidden = true;
        dock.setAttribute('aria-hidden', 'true');
        dock.innerHTML = '';
        return;
    }
    const livePreviews = previews.filter(preview => !String(preview.id || '').startsWith('placeholder:')).slice(0, 4);
    if (!livePreviews.length) {
        dock.hidden = true;
        dock.setAttribute('aria-hidden', 'true');
        dock.innerHTML = '';
        return;
    }
    dock.hidden = false;
    dock.setAttribute('aria-hidden', 'false');
    dock.innerHTML = livePreviews
        .map(preview => `<button type="button" data-test-preview-id="${preview.id}">${preview.title}</button>`)
        .join('');
}
function bindPreviewStatusEvents() {
    if (previewStatusBound)
        return;
    previewStatusBound = true;
    const recoveryBtn = document.getElementById('landingRecoveryBtn');
    if (recoveryBtn && !recoveryBtn.__ndwBound) {
        recoveryBtn.addEventListener('click', generateNew);
        recoveryBtn.__ndwBound = true;
    }
    const dock = document.getElementById('ndwTestPreviewDock');
    if (dock && !dock.__ndwBound) {
        dock.addEventListener('click', (event) => {
            const target = event.target;
            const button = target?.closest('[data-test-preview-id]');
            if (!button)
                return;
            const id = button.dataset.testPreviewId;
            if (id) {
                void loadPrefetchSite(id);
            }
        });
        dock.__ndwBound = true;
    }
    window.addEventListener('ndw:preview-status', (event) => {
        const detail = event.detail || {};
        const previews = Array.isArray(detail.previews) ? detail.previews : [];
        setLandingFallbackVisible(Boolean(document.body.classList.contains('landing-mode') && !detail.hasLivePreviews));
        renderTestPreviewDock(previews);
    });
}
async function primeTestPreviewStatus() {
    try {
        const resp = await fetch('/api/prefetch/previews?limit=6', { cache: 'no-store' });
        if (!resp.ok)
            throw new Error(`preview status failed: ${resp.status}`);
        const previews = await resp.json();
        const livePreviews = Array.isArray(previews) ? previews : [];
        window.dispatchEvent(new CustomEvent('ndw:preview-status', {
            detail: {
                hasLivePreviews: livePreviews.length > 0,
                count: livePreviews.length,
                previews: livePreviews,
            },
        }));
    }
    catch (error) {
        console.warn('[ndw] test preview priming failed', error);
        window.dispatchEvent(new CustomEvent('ndw:preview-status', {
            detail: {
                hasLivePreviews: false,
                count: 0,
                previews: [],
            },
        }));
    }
}
function parseRgb(color) {
    const match = color.match(/rgba?\(([^)]+)\)/);
    if (!match)
        return [255, 255, 255];
    const parts = match[1].split(',').map(part => Number(part.trim()));
    return [parts[0] ?? 255, parts[1] ?? 255, parts[2] ?? 255];
}
function relativeLuminance([r, g, b]) {
    const srgb = [r, g, b].map(v => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
}
function ensureReadableTheme(target) {
    try {
        const el = target || document.body;
        if (!el.isConnected)
            return;
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
            }
            else {
                // Dark background -> Force light text
                el.style.color = '#f8fafc';
            }
        }
    }
    catch (err) {
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
            if (document.body.classList.contains(cls))
                document.body.classList.remove(cls);
            if (document.documentElement.classList.contains(cls))
                document.documentElement.classList.remove(cls);
        });
    }
    catch (err) {
        console.warn('ensureScrollableBody failed', err);
    }
}
function ensureJsonOverlay() {
    if (document.getElementById('jsonOverlay'))
        return;
    const wrap = document.createElement('div');
    wrap.id = 'jsonOverlay';
    wrap.className = 'fixed top-3 right-3 z-50';
    wrap.innerHTML = `<button id="toggleJsonBtn" type="button" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs">Peek under the hood</button>
  <div id="jsonPanel" class="hidden mt-2 max-w-[60vw] max-h-[60vh] overflow-auto bg-white border border-slate-200 rounded shadow-lg p-3 text-slate-900">
    <pre id="jsonOut" class="text-[11px] whitespace-pre-wrap text-slate-900"></pre>
  </div>`;
    document.body.appendChild(wrap);
    const btn = document.getElementById('toggleJsonBtn');
    const panel = document.getElementById('jsonPanel');
    if (btn && panel) {
        btn.addEventListener('click', () => {
            panel.classList.toggle('hidden');
            btn.textContent = panel.classList.contains('hidden') ? 'Peek under the hood' : 'Close the hood';
        });
    }
}
export function updateJsonOut(data) {
    const jsonOut = document.getElementById('jsonOut');
    if (!jsonOut)
        return;
    try {
        jsonOut.textContent = JSON.stringify(data, null, 2);
    }
    catch (err) {
        jsonOut.textContent = String(err || 'Failed to stringify JSON');
    }
}
const TRANSITIONS = ['portal', 'iris', 'noise', 'warp', 'flash'];
let transitionIndex = 0;
let hasRenderedOnce = false;
let transitionInFlight = false;
function nextTransition() {
    const t = TRANSITIONS[transitionIndex % TRANSITIONS.length];
    transitionIndex += 1;
    return t;
}
export function __ndwTestResetTransitions() {
    transitionIndex = 0;
    hasRenderedOnce = false;
    transitionInFlight = false;
}
export function __ndwTestSetBodyMode(mode) {
    document.body.classList.toggle('landing-mode', mode === 'landing');
    document.body.classList.toggle('generated-mode', mode === 'generated');
}
export function __ndwTestEnsureFloatingGenerate() {
    ensureFloatingGenerate();
}
export async function __ndwTestRenderEvalDoc(doc, options = {}) {
    if (!NDW_TEST_MODE) {
        throw new Error('Eval render hook is only available in ndw_test mode.');
    }
    if (options.hideChrome === false) {
        document.body.classList.remove('ndw-eval-hide-chrome');
    }
    else {
        document.body.classList.add('ndw-eval-hide-chrome');
    }
    updateJsonOut(doc);
    hideHeroOverlay();
    hideLandingElements();
    await enterSite(doc);
    await sleep(Math.max(0, Number(options.settleMs ?? 0)));
    const hero = document.querySelector('.hero-wrap');
    const heroHidden = !hero || getComputedStyle(hero).display === 'none' || hero.classList.contains('is-hidden');
    return {
        ok: !Boolean(doc?.error),
        title: document.title,
        generatedMode: document.body.classList.contains('generated-mode'),
        heroHidden,
    };
}
function installEvalHook() {
    if (!NDW_TEST_MODE)
        return;
    _w.__ndwEvalRenderDoc = (doc, options) => __ndwTestRenderEvalDoc(doc, options || {});
}
function ensureTransitionStyles() {
    if (document.getElementById('ndw-transition-styles'))
        return;
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
function buildSnapshot() {
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
function getAccentColor() {
    try {
        const styles = getComputedStyle(document.body);
        const accent = styles.getPropertyValue('--accent-500').trim();
        if (accent)
            return accent;
        const primary = styles.getPropertyValue('--primary').trim();
        if (primary)
            return primary;
        const bg = styles.backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)')
            return bg;
    }
    catch (_) {
        // ignore
    }
    return '#facc15';
}
function cleanupCurrentWorld() {
    if (_w.NDW?._cleanup) {
        try {
            _w.NDW._cleanup();
        }
        catch (err) {
            console.warn('[ndw] cleanup error:', err);
        }
    }
    document.querySelectorAll('script[data-ndw-world-script="1"]').forEach(el => el.remove());
    document.querySelectorAll('style[data-ndw-sandbox="1"]').forEach(el => el.remove());
    document.getElementById('ndwSnippetError')?.remove();
}
async function runTransition(renderFn) {
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
    }
    catch (err) {
        console.error('[ndw] render error during transition', err);
    }
    await new Promise(requestAnimationFrame);
    const animations = [];
    const canAnimate = typeof snapshot.animate === 'function';
    const durations = {
        portal: 280,
        iris: 260,
        noise: 200,
        warp: 240,
        flash: 160,
    };
    const duration = durations[transition];
    if (canAnimate) {
        const fadeOut = snapshot.animate([
            { opacity: 1, transform: 'scale(1)', filter: 'blur(0px)' },
            { opacity: 0, transform: 'scale(1.01)', filter: 'blur(2px)' },
        ], { duration, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'forwards' });
        animations.push(fadeOut);
        const fadeIn = target.animate([
            { opacity: 0, transform: 'scale(0.992)', filter: 'blur(3px)' },
            { opacity: 1, transform: 'scale(1)', filter: 'blur(0px)' },
        ], { duration, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'forwards' });
        animations.push(fadeIn);
        if (transition === 'portal') {
            overlay.style.background =
                'radial-gradient(circle at 50% 50%, rgba(15,23,42,0.35) 0%, rgba(15,23,42,0.15) 35%, rgba(15,23,42,0) 70%)';
            overlay.style.clipPath = 'circle(0% at 50% 50%)';
            animations.push(overlay.animate([
                { opacity: 1, clipPath: 'circle(0% at 50% 50%)' },
                { opacity: 0, clipPath: 'circle(160% at 50% 50%)' },
            ], { duration, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', fill: 'forwards' }));
        }
        else if (transition === 'iris') {
            overlay.style.background =
                'radial-gradient(circle at 50% 50%, rgba(15,23,42,0.2) 0%, rgba(15,23,42,0) 60%)';
            animations.push(overlay.animate([
                { opacity: 0.6, transform: 'scale(0.75)' },
                { opacity: 0, transform: 'scale(1.4)' },
            ], { duration, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'forwards' }));
        }
        else if (transition === 'noise') {
            overlay.classList.add('ndw-transition-noise');
            animations.push(overlay.animate([
                { opacity: 0 },
                { opacity: 0.25 },
                { opacity: 0 },
            ], { duration: Math.max(180, duration), easing: 'linear', fill: 'forwards' }));
        }
        else if (transition === 'warp') {
            animations.push(snapshot.animate([
                { opacity: 1, filter: 'blur(0px)' },
                { opacity: 0, filter: 'blur(6px)' },
            ], { duration, easing: 'cubic-bezier(0.25, 0.6, 0.2, 1)', fill: 'forwards' }));
            animations.push(target.animate([
                { opacity: 0, filter: 'blur(6px)' },
                { opacity: 1, filter: 'blur(0px)' },
            ], { duration, easing: 'cubic-bezier(0.25, 0.6, 0.2, 1)', fill: 'forwards' }));
        }
        else if (transition === 'flash') {
            overlay.style.background = getAccentColor();
            animations.push(overlay.animate([
                { opacity: 0 },
                { opacity: 0.4 },
                { opacity: 0 },
            ], { duration: Math.max(150, duration), easing: 'ease-out', fill: 'forwards' }));
        }
        await Promise.all(animations.map(anim => anim.finished.catch(() => { })));
    }
    else {
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
    if (document.getElementById(id))
        return;
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
    if (__ndwAppInitialized)
        return;
    __ndwAppInitialized = true;
    mainEl = document.getElementById('appMain');
    console.debug('[ndw] app init; readyState=', document.readyState);
    window.addEventListener('message', handleGeneratedFrameMessage);
    ensureControlStyles();
    ensureJsonOverlay();
    installEvalHook();
    bindPreviewStatusEvents();
    ensureFloatingGenerate();
    ensureSitesCounterOverlay();
    refreshSitesCounter();
    renderLanding();
}
const API_KEY = (_w.API_KEY && String(_w.API_KEY)) || (bodyEl.dataset.apiKey && String(bodyEl.dataset.apiKey)) || '';
function buildAuthHeaders() {
    const headers = { 'content-type': 'application/json' };
    if (API_KEY) {
        headers['x-api-key'] = API_KEY;
    }
    return headers;
}
async function enterSite(doc) {
    const anyDoc = doc;
    if (anyDoc && typeof anyDoc.error === 'string') {
        showError(anyDoc.error);
        return;
    }
    if (anyDoc && anyDoc.kind === 'ndw_snippet_v1') {
        await runTransition(() => renderNdwSnippet(anyDoc));
        return;
    }
    if (anyDoc && anyDoc.kind === 'full_page_html' && typeof anyDoc.html === 'string' && anyDoc.html.trim()) {
        await runTransition(() => renderFullPage(anyDoc.html));
        return;
    }
    const comps = Array.isArray(anyDoc?.components) ? anyDoc.components : [];
    const first = comps.find((c) => c && c.props && typeof c.props.html === 'string' && c.props.html.trim());
    if (!first) {
        showError('No renderable HTML found');
        return;
    }
    await runTransition(() => renderInline(first.props.html));
}
export function renderDocForPreview(doc) {
    try {
        document.body.classList.add('generated-mode');
        document.body.classList.remove('landing-mode');
    }
    catch (_) {
        // Ignore DOM errors in headless preview mode.
    }
    void enterSite(doc);
}
async function callGenerate(brief, seed) {
    const resp = await fetch('/generate', { method: 'POST', headers: buildAuthHeaders(), body: JSON.stringify({ brief, seed }) });
    if (!resp.ok) {
        const text = await resp.text();
        return { error: `Generate failed (${resp.status}): ${text || resp.statusText}` };
    }
    return resp.json();
}
function setGenerating(is) {
    const controls = [
        document.getElementById('floatingGenerate'),
        document.getElementById('landingRecoveryBtn'),
        ...Array.from(document.querySelectorAll('[data-gen-button="1"]')),
    ].filter(Boolean);
    controls.forEach(b => {
        if (is) {
            b.setAttribute('aria-busy', 'true');
            b.classList.add('opacity-50', 'pointer-events-none');
        }
        else {
            b.removeAttribute('aria-busy');
            b.classList.remove('opacity-50', 'pointer-events-none');
        }
    });
}
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
async function closeShutter() {
    const shutter = document.getElementById('shutter');
    if (!shutter)
        return;
    shutter.classList.remove('shutter-open');
    shutter.classList.add('shutter-closed');
    await sleep(650);
}
async function openShutter() {
    const shutter = document.getElementById('shutter');
    if (!shutter)
        return;
    shutter.classList.remove('shutter-closed');
    shutter.classList.add('shutter-open');
    await sleep(650);
}
// Progressive Reveal: feature is fully disabled (kept as no-op for compatibility).
export async function prepareReveal() {
    const mainEl = document.getElementById('appMain');
    if (!mainEl)
        return;
    mainEl.style.opacity = '1';
}
export async function playReveal() {
    const mainEl = document.getElementById('appMain');
    if (!mainEl)
        return;
    mainEl.style.opacity = '1';
}
export function hideLandingElements() {
    const selectors = ['.blob-cont', '.noise-overlay', '#cursor-glow'];
    selectors.forEach(sel => {
        const el = document.querySelector(sel);
        if (el)
            el.remove();
    });
    setLandingFallbackVisible(false);
    renderTestPreviewDock([]);
    const tunnelContainer = document.getElementById('tunnel-container');
    if (tunnelContainer)
        tunnelContainer.style.display = 'none';
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
    if (_w.__ndwLandingCues)
        return;
    const hint = document.getElementById('heroHint');
    const cue = document.getElementById('scrollCue');
    if (!hint && !cue)
        return;
    _w.__ndwLandingCues = true;
    if (NDW_TEST_MODE) {
        hint?.classList.remove('is-hidden');
        cue?.classList.remove('is-hidden');
        return;
    }
    let hintTimer;
    let cueTimer;
    const hideAll = () => {
        if (hintTimer)
            window.clearTimeout(hintTimer);
        if (cueTimer)
            window.clearTimeout(cueTimer);
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
    hintTimer = window.setTimeout(() => hint?.classList.add('is-hidden'), 8000);
    cueTimer = window.setTimeout(() => cue?.classList.add('is-hidden'), 10000);
}
// export function _resetMainEl() {
//   mainEl = document.getElementById('appMain');
//   // console.error('[debug] _resetMainEl found:', mainEl?.id);
// }
let activeController = null;
_w.ndwGenerate = generateNew;
async function generateNew(e) {
    if (_w.__ndwGenerating) {
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
    if (e)
        e.preventDefault();
    const seed = Math.floor(Math.random() * 1e9);
    const jsonOut = document.getElementById('jsonOut');
    if (jsonOut)
        jsonOut.textContent = '';
    _w.__ndwGenerating = true;
    _w.__ndwTimedOut = false;
    setGenerating(true);
    if (mainEl)
        mainEl.innerHTML = '';
    await closeShutter();
    const panel = document.getElementById('jsonPanel');
    const btn = document.getElementById('toggleJsonBtn');
    if (panel && !panel.classList.contains('hidden')) {
        panel.classList.add('hidden');
        if (btn)
            btn.textContent = 'Peek under the hood';
    }
    const startTime = Date.now();
    const MIN_DELAY = 3000; // 3s optimistic opening fallback
    const PATIENCE_DELAY = 5000; // 5s: Update spinner text
    const DEADMAN_DELAY = 112000; // 112s: Give up
    let deadman;
    let optimisticTimer;
    let patienceTimer;
    let shutterOpened = false;
    // Optimistic Shutter Opening: If 3s pass, ONLY open if we have content ready
    optimisticTimer = setTimeout(async () => {
        // Only open if we actually have a page rendered (firstPageSeen)
        // If we haven't seen a page yet, we keep the shutter closed so we don't show a blank white screen.
        if (_w.__ndwGenerating && !_w.__ndwTimedOut && firstPageSeen && !shutterOpened) {
            console.debug('[ndw] Optimistic shutter opening triggered (content ready)');
            await openShutter();
            shutterOpened = true;
        }
    }, MIN_DELAY);
    // Patience Timer: If 5s pass and still nothing, reassure the user
    patienceTimer = setTimeout(() => {
        if (_w.__ndwGenerating && !firstPageSeen) {
            showSpinner('Connecting to deep logic…');
        }
    }, PATIENCE_DELAY);
    // Lifted to function scope for timer access
    let firstPageSeen = false;
    const renderFirstPage = async (page) => {
        clearTimeout(deadman);
        firstPageSeen = true;
        hideHeroOverlay();
        hideLandingElements();
        hideSpinner();
        updateJsonOut(page);
        const isFullPage = page && page.kind === 'full_page_html' && typeof page.html === 'string' && page.html.trim();
        if (isFullPage) {
            await runTransition(() => renderFullPage(page.html));
        }
        else {
            await enterSite(page);
        }
        if (!shutterOpened) {
            await openShutter();
            shutterOpened = true;
        }
    };
    const renderFollowupPage = async (page) => {
        const isFullPage = page && page.kind === 'full_page_html' && typeof page.html === 'string' && page.html.trim();
        if (isFullPage) {
            await runTransition(() => renderFullPage(page.html));
        }
        else {
            await enterSite(page);
        }
        updateJsonOut(page);
    };
    const handleEvent = async (event, data) => {
        if (event === 'page') {
            const page = data;
            if (!firstPageSeen) {
                await renderFirstPage(page);
            }
            else {
                await renderFollowupPage(page);
            }
        }
        else if (event === 'error') {
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
        if (deadman)
            clearTimeout(deadman);
        deadman = setTimeout(() => {
            if (!firstPageSeen) {
                console.error('[ndw] Shutter deadman triggered');
                _w.__ndwTimedOut = true;
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
        showSpinner('Art directing your next world…');
        const resp = await fetch('/generate/stream', {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({ brief: '', seed }),
            signal
        });
        if (!resp.ok)
            throw new Error(`Stream failed: ${resp.status}`);
        const reader = resp.body?.getReader();
        if (!reader)
            throw new Error('No reader');
        const decoder = new TextDecoder();
        let messageBuffer = '';
        let currentEvent = '';
        petDeadman();
        while (true) {
            const { done, value } = await reader.read();
            if (done)
                break;
            petDeadman();
            messageBuffer += decoder.decode(value, { stream: true });
            const lines = messageBuffer.split('\n');
            messageBuffer = lines.pop() || '';
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed)
                    continue;
                if (trimmed.startsWith('event: ')) {
                    currentEvent = trimmed.substring(7);
                }
                else if (trimmed.startsWith('data: ')) {
                    const dataStr = trimmed.substring(6);
                    try {
                        const data = JSON.parse(dataStr);
                        await handleEvent(currentEvent, data);
                    }
                    catch (e) {
                        console.warn('SSE parse error', e);
                    }
                }
                else if (trimmed.startsWith('{')) {
                    try {
                        const payload = JSON.parse(trimmed);
                        const event = payload?.event || '';
                        const data = payload?.data ?? payload;
                        if (event) {
                            await handleEvent(event, data);
                        }
                    }
                    catch (e) {
                        console.warn('NDJSON parse error', e);
                    }
                }
            }
        }
        if (!firstPageSeen) {
            // Stream ended but we never saw a page?
            clearTimeout(deadman);
            if (!_w.__ndwTimedOut) {
                showError('Connection closed before content was ready. Try again?');
                if (!shutterOpened) {
                    await openShutter();
                    shutterOpened = true;
                }
            }
        }
        ensureFloatingGenerate();
        adaptGenerateButtons();
    }
    catch (err) {
        console.error('[ndw] stream error', err);
        if (!_w.__ndwTimedOut && !firstPageSeen) {
            try {
                const fallback = await callGenerate('', seed);
                if (fallback && !fallback.error) {
                    await renderFirstPage(fallback);
                }
                else {
                    showError(fallback?.error || 'Generation failed. Please try again.');
                    if (!shutterOpened) {
                        await openShutter();
                        shutterOpened = true;
                    }
                }
            }
            catch (fallbackErr) {
                console.error('[ndw] fallback generate failed', fallbackErr);
                showError('Generation failed. Please try again.');
                if (!shutterOpened) {
                    await openShutter();
                    shutterOpened = true;
                }
            }
        }
        else if (!_w.__ndwTimedOut) {
            showError('Generation failed. Please try again.');
            if (!shutterOpened) {
                await openShutter();
                shutterOpened = true;
            }
        }
    }
    finally {
        if (deadman)
            clearTimeout(deadman);
        if (optimisticTimer)
            clearTimeout(optimisticTimer);
        if (patienceTimer)
            clearTimeout(patienceTimer);
        setGenerating(false);
        _w.__ndwGenerating = false;
        activeController = null;
        hideSpinner();
    }
}
// Utility to render content to a specific target element
function renderToTarget(html, target) {
    target.innerHTML = '';
    target.appendChild(buildGeneratedFrame(html));
}
function ensureFloatingGenerate() {
    console.debug('[ndw] ensureFloatingGenerate called');
    if (document.body.classList.contains('landing-mode')) {
        const existingWrap = document.getElementById('floatingGenerateWrap');
        if (existingWrap) {
            try {
                existingWrap.remove();
            }
            catch (_) { }
        }
        return;
    }
    document.getElementById('floatingGenerateWrap')?.remove();
    ensureSitesCounterOverlay();
    const generateWrap = document.createElement('div');
    generateWrap.id = 'floatingGenerateWrap';
    generateWrap.innerHTML = buildFloatingGenerateMarkup();
    document.body.appendChild(generateWrap);
    document.getElementById('floatingGenerate')?.addEventListener('click', generateNew);
}
let tunnel = null;
export function __ndwResolveTunnelCardAction(id) {
    return String(id || '').startsWith('placeholder:') ? 'generate' : 'prefetch';
}
async function initTunnel() {
    const container = document.getElementById('tunnel-container');
    if (container && !tunnel) {
        const { InfiniteTunnel } = await import('./tunnel.js');
        tunnel = new InfiniteTunnel(container);
        tunnel.setOnCardClick((id) => {
            if (__ndwResolveTunnelCardAction(id) === 'generate') {
                void generateNew();
                return;
            }
            void loadPrefetchSite(id);
        });
        await tunnel.init();
        tunnel.setTheme(false); // Default to light mode for tunnel
    }
}
async function loadPrefetchSite(id) {
    if (_w.__ndwGenerating)
        return;
    console.debug(`[ndw] loading queued site ${id}`);
    // Close shutter to transition
    await closeShutter();
    try {
        const resp = await fetch(`/api/prefetch/${encodeURIComponent(id)}`);
        if (!resp.ok)
            throw new Error(`Prefetch load failed: ${resp.status}`);
        const page = await resp.json();
        hideHeroOverlay();
        hideLandingElements();
        updateJsonOut(page);
        // Clear tunnel if we are leaving landing (optional, or keep it for back nav)
        // For now we keep it in background but hidden by full page content
        await enterSite(page);
        // Open shutter
        await openShutter();
    }
    catch (e) {
        console.error('Prefetch load error:', e);
        showError('Failed to load site from queue.');
        await openShutter();
    }
}
function lockHeroOverlay() {
    const hero = document.querySelector('.hero-wrap');
    if (!hero)
        return;
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
    const container = hero.querySelector('.container');
    if (container) {
        container.style.pointerEvents = 'auto';
    }
}
function hideHeroOverlay() {
    const hero = document.querySelector('.hero-wrap');
    if (!hero)
        return;
    hero.classList.add('is-hidden');
    setLandingFallbackVisible(false);
    document.body.classList.remove('landing-mode');
    document.body.classList.add('generated-mode');
}
function showHeroOverlay() {
    const hero = document.querySelector('.hero-wrap');
    if (!hero)
        return;
    hero.classList.remove('is-hidden');
    document.body.classList.add('landing-mode');
    document.body.classList.remove('generated-mode');
}
function renderLanding() {
    destroyActiveSiteFrame();
    setLandingFallbackVisible(false);
    renderTestPreviewDock([]);
    if (NDW_TEST_MODE) {
        void primeTestPreviewStatus();
    }
    else {
        // Initialize 3D Tunnel
        initTunnel().catch(e => console.error('[ndw] Tunnel init failed', e));
    }
    lockHeroOverlay();
    showHeroOverlay();
    setupLandingCues();
}
function ensureSitesCounterOverlay() {
    if (document.getElementById('sitesCounterFloating'))
        return;
    const wrap = document.createElement('div');
    wrap.id = 'sitesCounterFloating';
    wrap.className = 'ndw-sites-panel';
    wrap.innerHTML = `
    <div id="sitesCounterBadge" class="ndw-sites-badge">Sites generated: 0</div>
    <div id="sitesCounterModeMount" class="ndw-sites-mode-mount"></div>
  `;
    document.body.appendChild(wrap);
}
async function refreshSitesCounter() {
    try {
        const badge = document.getElementById('sitesCounterBadge');
        const resp = await fetch(`/metrics/total?ts=${Date.now()}`, {
            headers: { accept: 'application/json' },
            cache: 'no-store',
        });
        if (!resp.ok)
            throw new Error(String(resp.status));
        const data = await resp.json();
        const n = typeof data?.total === 'number' ? data.total : 0;
        if (badge)
            badge.textContent = `Sites generated: ${n}`;
    }
    catch { }
}
function autoInitIfEnabled() {
    if (_w.__ndwDisableAutoInit)
        return;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initApp);
    }
    else {
        initApp();
    }
}
autoInitIfEnabled();
// Update browser tab title without showing an on-page overlay.
function upsertTitleOverlay(title) {
    const existing = document.getElementById('ndw-title');
    if (existing && existing.parentNode) {
        existing.parentNode.removeChild(existing);
    }
    if (typeof title === 'string' && title.trim()) {
        document.title = title.trim();
    }
}
function escapeHtml(s) { return s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'); }
function resetFullPageHostRoot(target) {
    if (!target)
        return;
    target.removeAttribute('style');
    target.className = 'w-full min-h-screen';
    target.removeAttribute('data-ndw-fullpage-root');
}
function postRenderCommon() {
    ensureFloatingGenerate();
    ensureSitesCounterOverlay();
    adaptGenerateButtons();
    ensureScrollableBody();
    upsertTitleOverlay(undefined);
    try {
        window.lucide?.createIcons();
    }
    catch (_) { }
}
function destroyActiveSiteFrame() {
    if (activeSiteFrame && activeSiteFrame.parentNode) {
        activeSiteFrame.remove();
    }
    activeSiteFrame = null;
}
function handleGeneratedFrameMessage(event) {
    const data = event.data;
    if (!data || typeof data !== 'object' || data.type !== 'NDW_GENERATE')
        return;
    void generateNew();
}
function renderFullPage(html) {
    try {
        document.querySelectorAll('style[data-gen-style="1"], style[data-ndw-sandbox="1"]').forEach(s => s.remove());
        document.body.style.cssText = '';
        const hostClasses = ['ndw-base', 'generated-mode', 'ndw-eval-hide-chrome'];
        const currentClasses = Array.from(document.body.classList);
        const toKeep = currentClasses.filter(c => hostClasses.includes(c));
        document.body.className = toKeep.join(' ');
        hideLandingElements();
        document.body.classList.add('generated-mode');
        const target = resolveMainEl();
        destroyActiveSiteFrame();
        resetFullPageHostRoot(target);
        if (target) {
            target.innerHTML = '';
            activeSiteFrame = buildGeneratedFrame(html);
            target.appendChild(activeSiteFrame);
        }
        const title = extractDocumentTitle(html);
        if (title) {
            document.title = title;
        }
        postRenderCommon();
    }
    catch (e) {
        console.error('Full-page render error:', e);
        showError('Failed to render content.');
    }
}
function renderInline(html) {
    try {
        renderFullPage(html);
    }
    catch (e) {
        console.error('Inline render error:', e);
        showError('Failed to render content.');
    }
}
function renderNdwSnippet(snippet) {
    try {
        const title = escapeHtml(snippet.title || 'Generated website');
        const snippetBg = snippet.background || {};
        const bgStyle = typeof snippetBg.style === 'string' ? snippetBg.style : '';
        const bgClass = typeof snippetBg.class === 'string' ? snippetBg.class : '';
        const html = `
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
  <link rel="stylesheet" href="/tailwind.css">
  <script src="/js/ndw.js"></script>
  <style>
    html, body { margin: 0; min-height: 100%; }
    body { ${bgStyle || 'background: linear-gradient(135deg,#f1f5f9,#e2e8f0); color: #0f172a;'} }
    ${snippet.css || ''}
  </style>
</head>
<body class="${escapeHtml(bgClass)}">
  <main id="ndw-content">${snippet.html || '<canvas id="canvas"></canvas>'}</main>
  <script>${snippet.js || ''}</script>
</body>
</html>`;
        renderFullPage(html);
        return;
    }
    catch (e) {
        console.error('NDW snippet render error:', e);
        showError('Failed to render snippet.');
    }
}
function showError(msg) { const target = resolveMainEl(); if (!target)
    return; const wrap = document.createElement('div'); wrap.className = 'max-w-xl mx-auto mt-8 px-4'; wrap.innerHTML = `<div class="p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">${escapeHtml(String(msg || 'Error'))}</div>`; target.innerHTML = ''; target.appendChild(wrap); }
let __genBtnSeq = 0;
function buildUiverseButton(id) { const wrap = document.createElement('div'); wrap.className = 'inline-block align-middle'; wrap.innerHTML = `<div class="ndw-button button" aria-label="Generate"><button ${id ? `id="${id}"` : ''} data-gen-button="1" name="checkbox" type="button" aria-label="Generate"></button><span></span><span></span><span></span><span></span></div>`; return wrap; }
function looksLikeGenerate(el) {
    const datasetTrigger = (el.dataset?.ndwTrigger || '').toLowerCase();
    if (datasetTrigger === 'new-site' || datasetTrigger === 'generate')
        return true;
    if (el.dataset?.ndwNoHijack === '1')
        return false;
    const label = (el.getAttribute('aria-label') || el.textContent || '')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();
    const id = (el.id || '').trim().toLowerCase();
    const cls = (el.className || '').toLowerCase();
    if (id === 'landinggenerate' || id === 'floatinggenerate')
        return false;
    if (el.closest('.button'))
        return false;
    const explicitLabels = new Set(['generate', 'generate website', 'generate a website', 'new site', 'new website']);
    if (explicitLabels.has(label))
        return true;
    const explicitIds = new Set(['generate', 'generate-website', 'generatewebsite', 'ndw-generate', 'new-site']);
    if (explicitIds.has(id))
        return true;
    if (/\bndw-(?:global-)?generate\b/.test(cls))
        return true;
    return false;
}
function adaptGenerateButtons() {
    const scope = mainEl || document;
    const candidates = Array.from(scope.querySelectorAll('button, a[role="button"], a[href="#generate"], input[type="button"], input[type="submit"]'));
    candidates.forEach(el => {
        if (!looksLikeGenerate(el))
            return;
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
    if (!el) {
        el = document.createElement('div');
        el.id = 'gen-spinner';
        el.className = 'hidden fixed inset-0 grid place-items-center bg-black/40 z-50';
        el.innerHTML = `<div class="flex flex-col items-center gap-3 text-white"><div class="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent"></div><div id="spinnerMsg" class="text-sm">Generating…</div></div>`;
        document.body.appendChild(el);
    }
    return el;
}
function showSpinner(msg) { const el = ensureSpinner(); const m = document.getElementById('spinnerMsg'); if (m && msg)
    m.textContent = msg; el.classList.remove('hidden'); }
function hideSpinner() { ensureSpinner().classList.add('hidden'); }
const _origEnterSite = enterSite;
async function enterSiteWithCounter(doc) {
    await _origEnterSite(doc);
    if (doc && !doc.error) {
        await refreshSitesCounter();
    }
}
// @ts-ignore
enterSite = enterSiteWithCounter;
