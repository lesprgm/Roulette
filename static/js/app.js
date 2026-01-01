const _w = window;
const bodyEl = document.body;
const mainEl = document.getElementById('appMain');
console.debug('[ndw] app script evaluated; readyState=', document.readyState);
const SANDBOX_SCOPE = '#ndw-sandbox';
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
    wrap.innerHTML = `<button id="toggleJsonBtn" type="button" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs">Show JSON</button>
  <div id="jsonPanel" class="hidden mt-2 max-w-[60vw] max-h-[60vh] overflow-auto bg-white border border-slate-200 rounded shadow-lg p-3 text-slate-900">
    <pre id="jsonOut" class="text-[11px] whitespace-pre-wrap text-slate-900"></pre>
  </div>`;
    document.body.appendChild(wrap);
    const btn = document.getElementById('toggleJsonBtn');
    const panel = document.getElementById('jsonPanel');
    if (btn && panel) {
        btn.addEventListener('click', () => {
            panel.classList.toggle('hidden');
            btn.textContent = panel.classList.contains('hidden') ? 'Show JSON' : 'Hide JSON';
        });
    }
}
ensureJsonOverlay();
ensureControlStyles();
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
#floatingGenerateWrap{position:fixed;left:50%;transform:translateX(-50%);bottom:24px;z-index:9999;}
`;
    document.head.appendChild(style);
}
function scopeCssText(cssText, scope) {
    if (!cssText.trim())
        return cssText;
    let styleEl = null;
    try {
        styleEl = document.createElement('style');
        styleEl.textContent = cssText;
        document.head.appendChild(styleEl);
        const sheet = styleEl.sheet;
        if (!sheet)
            return cssText;
        const scoped = processCssRules(Array.from(sheet.cssRules), scope);
        return scoped.join('\n');
    }
    catch (err) {
        console.warn('scopeCssText failed', err);
        return cssText;
    }
    finally {
        styleEl?.remove();
    }
}
function processCssRules(rules, scope) {
    const output = [];
    rules.forEach(rule => {
        switch (rule.type) {
            case CSSRule.STYLE_RULE: {
                const styleRule = rule;
                const selectors = styleRule.selectorText.split(',').map(sel => {
                    let trimmed = sel.trim();
                    if (!trimmed)
                        return '';
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
                const mediaRule = rule;
                const inner = processCssRules(Array.from(mediaRule.cssRules), scope);
                output.push(`@media ${mediaRule.conditionText} { ${inner.join(' ')} }`);
                break;
            }
            case CSSRule.SUPPORTS_RULE: {
                const supportsRule = rule;
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
function scopeInlineStyles(container, scope) {
    const styles = Array.from(container.querySelectorAll('style'));
    styles.forEach(styleEl => {
        const scoped = scopeCssText(styleEl.textContent || '', scope);
        styleEl.textContent = scoped;
        styleEl.setAttribute('data-ndw-scoped', '1');
    });
}
const API_KEY = (_w.API_KEY && String(_w.API_KEY)) || (bodyEl.dataset.apiKey && String(bodyEl.dataset.apiKey)) || 'demo_123';
function stripExternalScripts(html) {
    return String(html).replace(/<script[^>]*\bsrc\s*=\s*['"][^'"]+['"][^>]*>\s*<\/script>/gi, '');
}
function containsDomReadyHook(code) {
    return /DOMContentLoaded/i.test(code);
}
function invokeDomReadyListener(listener) {
    try {
        const evt = new Event('DOMContentLoaded');
        Object.defineProperty(evt, 'target', { value: document, configurable: true });
        Object.defineProperty(evt, 'currentTarget', { value: document, configurable: true });
        if (typeof listener === 'function') {
            listener.call(document, evt);
        }
        else if (listener && typeof listener.handleEvent === 'function') {
            listener.handleEvent.call(listener, evt);
        }
    }
    catch (err) {
        console.warn('ndw dom-ready handler error', err);
    }
}
function executeDocScripts(scripts, target) {
    scripts.forEach(old => {
        if (old.src) {
            const src = old.src.toLowerCase();
            const safe = src.includes('cdn.tailwindcss.com') || src.includes('unpkg.com') || src.includes('cdnjs.cloudflare.com/ajax/libs/gsap');
            if (!safe)
                return;
            if (document.querySelector(`script[src="${old.src}"]`))
                return;
            const sc = document.createElement('script');
            sc.src = old.src;
            if (old.type)
                sc.type = old.type;
            sc.async = false;
            document.head.appendChild(sc);
            return;
        }
        const code = old.textContent || '';
        const exec = () => {
            const sc = document.createElement('script');
            if (old.type)
                sc.type = old.type;
            sc.textContent = code;
            target?.appendChild(sc);
        };
        if (containsDomReadyHook(code)) {
            runWithPatchedDomReady(exec);
        }
        else {
            exec();
        }
    });
}
function runWithPatchedDomReady(exec) {
    if (document.readyState === 'loading') {
        exec();
        return;
    }
    const originalAdd = document.addEventListener.bind(document);
    const originalRemove = document.removeEventListener.bind(document);
    const intercepted = new Set();
    function patchedAdd(type, listener, options) {
        if (type === 'DOMContentLoaded' && listener) {
            intercepted.add(listener);
            invokeDomReadyListener(listener);
            return;
        }
        originalAdd(type, listener, options);
    }
    function patchedRemove(type, listener, options) {
        if (type === 'DOMContentLoaded' && listener) {
            intercepted.delete(listener);
            return;
        }
        originalRemove(type, listener, options);
    }
    document.addEventListener = patchedAdd;
    document.removeEventListener = patchedRemove;
    try {
        exec();
    }
    finally {
        document.addEventListener = originalAdd;
        document.removeEventListener = originalRemove;
        intercepted.clear();
    }
}
function enterSite(doc) {
    const anyDoc = doc;
    if (anyDoc && typeof anyDoc.error === 'string')
        return showError(anyDoc.error);
    if (anyDoc && anyDoc.kind === 'ndw_snippet_v1')
        return renderNdwSnippet(anyDoc);
    if (anyDoc && anyDoc.kind === 'full_page_html' && typeof anyDoc.html === 'string' && anyDoc.html.trim())
        return renderFullPage(anyDoc.html);
    const comps = Array.isArray(anyDoc?.components) ? anyDoc.components : [];
    const first = comps.find((c) => c && c.props && typeof c.props.html === 'string' && c.props.html.trim());
    if (!first)
        return showError('No renderable HTML found');
    renderInline(first.props.html);
}
async function callGenerate(brief, seed) {
    const resp = await fetch('/generate', { method: 'POST', headers: { 'content-type': 'application/json', 'x-api-key': API_KEY }, body: JSON.stringify({ brief, seed }) });
    if (!resp.ok) {
        const text = await resp.text();
        return { error: `Generate failed (${resp.status}): ${text || resp.statusText}` };
    }
    return resp.json();
}
function setGenerating(is) {
    const coreBtns = [document.getElementById('landingGenerate'), document.getElementById('floatingGenerate')].filter(Boolean);
    const inlineBtns = Array.from(document.querySelectorAll('[data-gen-button="1"]'));
    [...coreBtns, ...inlineBtns].forEach(b => {
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
function ensureShutter() {
    let top = document.getElementById('ndw-shutter-top');
    let bot = document.getElementById('ndw-shutter-bot');
    if (!top) {
        top = document.createElement('div');
        top.id = 'ndw-shutter-top';
        Object.assign(top.style, { position: 'fixed', top: '0', left: '0', width: '100%', height: '50%', background: '#0f172a', zIndex: '99999', transform: 'translateY(-100%)' });
        document.body.appendChild(top);
    }
    if (!bot) {
        bot = document.createElement('div');
        bot.id = 'ndw-shutter-bot';
        Object.assign(bot.style, { position: 'fixed', bottom: '0', left: '0', width: '100%', height: '50%', background: '#0f172a', zIndex: '99999', transform: 'translateY(100%)' });
        document.body.appendChild(bot);
    }
    return { top, bot };
}
async function closeShutter() {
    const { top, bot } = ensureShutter();
    const gsap = window.gsap;
    if (!gsap)
        return;
    return gsap.to([top, bot], { translateY: '0%', duration: 0.5, ease: 'power4.inOut' });
}
async function openShutter() {
    const { top, bot } = ensureShutter();
    const gsap = window.gsap;
    if (!gsap)
        return;
    return gsap.to(top, { translateY: '-100%', duration: 0.6, ease: 'power4.inOut' })
        .then(() => gsap.to(bot, { translateY: '100%', duration: 0.6, ease: 'power4.inOut', delay: -0.5 }));
}
_w.ndwGenerate = generateNew;
async function generateNew(e) {
    console.debug('[ndw] generateNew invoked (streaming burst)');
    if (e)
        e.preventDefault();
    const seed = Math.floor(Math.random() * 1e9);
    const jsonOut = document.getElementById('jsonOut');
    if (jsonOut)
        jsonOut.textContent = '';
    setGenerating(true);
    await closeShutter();
    const panel = document.getElementById('jsonPanel');
    const btn = document.getElementById('toggleJsonBtn');
    if (panel && !panel.classList.contains('hidden')) {
        panel.classList.add('hidden');
        if (btn)
            btn.textContent = 'Show JSON';
    }
    let deadman;
    try {
        const resp = await fetch('/generate/stream', {
            method: 'POST',
            headers: { 'content-type': 'application/json', 'x-api-key': API_KEY },
            body: JSON.stringify({ brief: '', seed })
        });
        if (!resp.ok)
            throw new Error(`Stream failed: ${resp.status}`);
        const reader = resp.body?.getReader();
        if (!reader)
            throw new Error('No reader');
        const decoder = new TextDecoder();
        let buffer = '';
        let firstPageSeen = false;
        // Safety: If no page arrives in 6s, force open
        deadman = setTimeout(() => {
            if (!firstPageSeen) {
                console.error('[ndw] Shutter deadman triggered');
                showError('Generation timed out');
                openShutter();
                setGenerating(false);
            }
        }, 6000);
        while (true) {
            const { done, value } = await reader.read();
            if (done)
                break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
                if (!line.trim())
                    continue;
                try {
                    const chunk = JSON.parse(line);
                    if (chunk.event === 'page') {
                        const page = chunk.data;
                        if (!firstPageSeen) {
                            clearTimeout(deadman);
                            enterSite(page);
                            firstPageSeen = true;
                            await openShutter();
                        }
                        if (jsonOut) {
                            jsonOut.textContent += (jsonOut.textContent ? '\n\n' : '') + JSON.stringify(page, null, 2);
                        }
                    }
                    else if (chunk.event === 'error') {
                        clearTimeout(deadman);
                        showError(chunk.data.error || 'Unknown streaming error');
                        await openShutter();
                    }
                }
                catch (err) {
                    console.warn('Chunk parse error', err);
                }
            }
        }
        if (!firstPageSeen) {
            // Stream ended but we never saw a page?
            clearTimeout(deadman);
            showError('Stream ended without content');
            await openShutter();
        }
        ensureFloatingGenerate();
        adaptGenerateButtons();
    }
    catch (err) {
        if (deadman)
            clearTimeout(deadman);
        console.error('Generate error:', err);
        showError(String(err));
        await openShutter();
    }
    finally {
        setGenerating(false);
    }
}
function ensureFloatingGenerate() {
    console.debug('[ndw] ensureFloatingGenerate called');
    const existing = document.getElementById('floatingGenerateWrap');
    if (existing)
        existing.remove();
    else {
        const oldBtn = document.getElementById('floatingGenerate');
        if (oldBtn) {
            const parent = oldBtn.closest('#floatingGenerateWrap') || oldBtn.parentElement || oldBtn;
            try {
                parent.remove();
            }
            catch (_) { }
        }
    }
    const wrap = document.createElement('div');
    wrap.id = 'floatingGenerateWrap';
    wrap.className = 'fixed left-1/2 -translate-x-1/2 bottom-6 z-50';
    wrap.innerHTML = `<div class="ndw-button button" aria-label="Generate"><button id="floatingGenerate" name="checkbox" type="button" aria-label="Generate"></button><span></span><span></span><span></span><span></span></div>`;
    document.body.appendChild(wrap);
    document.getElementById('floatingGenerate')?.addEventListener('click', generateNew);
}
ensureFloatingGenerate();
function renderLanding() {
    const btn = document.getElementById('landingGenerate');
    if (!btn)
        return;
    if (btn.__ndwBound)
        return;
    btn.addEventListener('click', generateNew);
    btn.__ndwBound = true;
    console.debug('[ndw] landingGenerate bound');
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { console.debug('[ndw] DOMContentLoaded'); renderLanding(); });
}
else {
    renderLanding();
}
function ensureSitesCounterOverlay() {
    if (document.getElementById('sitesCounterFloating'))
        return;
    const wrap = document.createElement('div');
    wrap.id = 'sitesCounterFloating';
    wrap.className = 'fixed right-3 top-16 z-50';
    wrap.innerHTML = `<div id="sitesCounterBadge" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs shadow border border-slate-700/50">Sites generated: 0</div>`;
    document.body.appendChild(wrap);
}
ensureSitesCounterOverlay();
async function refreshSitesCounter() {
    try {
        const el = document.getElementById('sitesCounter');
        const badge = document.getElementById('sitesCounterBadge');
        const resp = await fetch('/metrics/total', { headers: { accept: 'application/json' } });
        if (!resp.ok)
            throw new Error(String(resp.status));
        const data = await resp.json();
        const n = typeof data?.total === 'number' ? data.total : 0;
        if (el)
            el.textContent = `Sites generated: ${n}`;
        if (badge)
            badge.textContent = `Sites generated: ${n}`;
    }
    catch { }
}
refreshSitesCounter();
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
function renderFullPage(html) {
    try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(String(html), 'text/html');
        document.querySelectorAll('style[data-gen-style="1"]').forEach(s => s.remove());
        doc.head?.querySelectorAll('style').forEach(s => { const st = document.createElement('style'); st.setAttribute('data-gen-style', '1'); st.textContent = s.textContent || ''; document.head.appendChild(st); });
        document.body.style.cssText = '';
        // Do NOT wipe document.body.className completely to protect host classes like ndw-base
        const hostClasses = ['ndw-base'];
        const currentClasses = Array.from(document.body.classList);
        const toKeep = currentClasses.filter(c => hostClasses.includes(c));
        document.body.className = toKeep.join(' ');
        if (doc.body) {
            const newStyle = doc.body.getAttribute('style');
            const newClass = doc.body.getAttribute('class');
            if (newStyle)
                document.body.style.cssText = newStyle;
            if (newClass) {
                newClass.split(/\s+/).forEach(c => {
                    if (c.trim())
                        document.body.classList.add(c.trim());
                });
            }
        }
        if (mainEl) {
            mainEl.innerHTML = '';
            const frag = document.createDocumentFragment();
            const nodes = doc.body ? Array.from(doc.body.childNodes) : [];
            nodes.forEach(n => frag.appendChild(n.cloneNode(true)));
            mainEl.appendChild(frag);
        }
        const scripts = [];
        if (doc.head)
            scripts.push(...Array.from(doc.head.querySelectorAll('script')));
        if (doc.body)
            scripts.push(...Array.from(doc.body.querySelectorAll('script')));
        executeDocScripts(scripts, mainEl);
        ensureFloatingGenerate();
        ensureSitesCounterOverlay();
        adaptGenerateButtons();
        ensureScrollableBody();
        upsertTitleOverlay(undefined);
        ensureReadableTheme();
        try {
            window.lucide?.createIcons();
        }
        catch (_) { }
    }
    catch (e) {
        console.error('Full-page render error:', e);
        showError('Failed to render content.');
    }
}
function renderInline(html) {
    try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(String(html), 'text/html');
        doc.head?.querySelectorAll('style').forEach(s => { const st = document.createElement('style'); st.setAttribute('data-gen-style', '1'); st.textContent = s.textContent || ''; document.head.appendChild(st); });
        if (mainEl) {
            mainEl.innerHTML = '';
            const frag = document.createDocumentFragment();
            const nodes = doc.body ? Array.from(doc.body.childNodes) : [];
            nodes.forEach(n => frag.appendChild(n.cloneNode(true)));
            mainEl.appendChild(frag);
        }
        const scripts = [];
        if (doc.head)
            scripts.push(...Array.from(doc.head.querySelectorAll('script')));
        if (doc.body)
            scripts.push(...Array.from(doc.body.querySelectorAll('script')));
        executeDocScripts(scripts, mainEl);
        ensureFloatingGenerate();
        ensureSitesCounterOverlay();
        adaptGenerateButtons();
        ensureScrollableBody();
        upsertTitleOverlay(undefined);
        ensureReadableTheme();
        try {
            window.lucide?.createIcons();
        }
        catch (_) { }
    }
    catch (e) {
        console.error('Inline render error:', e);
        showError('Failed to render content.');
    }
}
function renderNdwSnippet(snippet) {
    try {
        const bg = snippet.background || {};
        const hasBg = (typeof bg.style === 'string' && bg.style.trim()) || (typeof bg.class === 'string' && bg.class.trim());
        document.querySelectorAll('style[data-ndw-sandbox="1"]').forEach(s => s.remove());
        if (mainEl) {
            mainEl.innerHTML = '';
            const sandbox = document.createElement('div');
            sandbox.id = 'ndw-sandbox';
            sandbox.className = 'ndw-sandbox';
            sandbox.style.position = 'relative';
            sandbox.style.minHeight = '60vh';
            sandbox.style.padding = '24px';
            sandbox.style.background = 'linear-gradient(135deg,#f1f5f9,#e2e8f0)';
            sandbox.style.color = '#0f172a';
            if (hasBg) {
                if (bg.style) {
                    sandbox.setAttribute('style', `${sandbox.getAttribute('style') || ''}; ${bg.style}`.trim());
                }
                if (bg.class) {
                    sandbox.className = `${sandbox.className} ${bg.class}`.trim();
                }
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
                    if (cls)
                        appRoot.className = `${appRoot.className} ${cls}`.trim();
                    if (sty)
                        appRoot.setAttribute('style', `${appRoot.getAttribute('style') || ''}; ${sty}`.trim());
                    const kids = Array.from(nested.childNodes);
                    nested.remove();
                    kids.forEach(n => appRoot.appendChild(n));
                }
            }
            else if (!hasCanvasCreation) {
                const c = document.createElement('canvas');
                c.id = 'canvas';
                c.style.display = 'block';
                c.style.width = '100%';
                c.style.minHeight = '60vh';
                appRoot.appendChild(c);
            }
            mainEl.appendChild(sandbox);
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
            if (!_w.NDW)
                console.warn('NDW runtime not found; snippet JS may fail.');
            if (!_w.__NDW_showSnippetErrorOverlay) {
                _w.__NDW_showSnippetErrorOverlay = (err) => {
                    try {
                        let el = document.getElementById('ndwSnippetError');
                        if (!el) {
                            el = document.createElement('div');
                            el.id = 'ndwSnippetError';
                            Object.assign(el.style, { position: 'fixed', top: '12px', left: '12px', zIndex: '1000', background: 'rgba(220,38,38,0.95)', color: '#fff', padding: '10px 12px', borderRadius: '8px', font: '12px/1.4 system-ui, sans-serif', boxShadow: '0 6px 20px rgba(0,0,0,0.25)', maxWidth: '60vw' });
                            el.innerHTML = '<strong>Snippet error</strong><div id="ndwSnippetErrorMsg" style="margin-top:6px;white-space:pre-wrap"></div>';
                            document.body.appendChild(el);
                        }
                        const msg = document.getElementById('ndwSnippetErrorMsg');
                        if (msg)
                            msg.textContent = String(err && (err.message || err)).slice(0, 500);
                    }
                    catch (e) {
                        console.error('Snippet error overlay failure', e);
                    }
                };
            }
            const rawJs = snippet.js;
            const execSnippet = () => {
                const sc = document.createElement('script');
                sc.type = 'text/javascript';
                sc.textContent = `(function(){try
{${rawJs}
}catch(err){try{(window.__NDW_showSnippetErrorOverlay||console.error).call(window,err);}catch(_){console.error(err);}}})();`;
                document.body.appendChild(sc);
            };
            if (rawJs && containsDomReadyHook(rawJs)) {
                runWithPatchedDomReady(execSnippet);
            }
            else {
                execSnippet();
            }
        }
        ensureFloatingGenerate();
        ensureSitesCounterOverlay();
        adaptGenerateButtons();
        ensureScrollableBody();
        const sandboxEl = document.getElementById('ndw-sandbox');
        if (sandboxEl instanceof HTMLElement)
            ensureReadableTheme(sandboxEl);
        try {
            window.lucide?.createIcons();
        }
        catch (_) { }
    }
    catch (e) {
        console.error('NDW snippet render error:', e);
        showError('Failed to render snippet.');
    }
}
function showError(msg) { if (!mainEl)
    return; const wrap = document.createElement('div'); wrap.className = 'max-w-xl mx-auto mt-8 px-4'; wrap.innerHTML = `<div class="p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">${escapeHtml(String(msg || 'Error'))}</div>`; mainEl.innerHTML = ''; mainEl.appendChild(wrap); }
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
function enterSiteWithCounter(doc) { _origEnterSite(doc); if (doc && !doc.error)
    refreshSitesCounter(); }
// @ts-ignore
enterSite = enterSiteWithCounter;
export {};
