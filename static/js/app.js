(function () {
  const $ = (sel) => document.querySelector(sel);
  const bodyEl = document.body;
  const mainEl = document.getElementById('appMain');
  const landingBtn = document.getElementById('landingGenerate');

  // JSON overlay (small toggle in top-right)
  function ensureJsonOverlay() {
    if (document.getElementById('jsonOverlay')) return;
    const wrap = document.createElement('div');
    wrap.id = 'jsonOverlay';
    wrap.className = 'fixed top-3 right-3 z-50';
    wrap.innerHTML = `
      <button id="toggleJsonBtn" type="button" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs">Show JSON</button>
      <div id="jsonPanel" class="hidden mt-2 max-w-[60vw] max-h-[60vh] overflow-auto bg-white/95 border border-slate-200 rounded shadow-lg p-3">
        <pre id="jsonOut" class="text-[11px] whitespace-pre-wrap"></pre>
      </div>`;
    document.body.appendChild(wrap);
    const btn = document.getElementById('toggleJsonBtn');
    const panel = document.getElementById('jsonPanel');
    btn.addEventListener('click', () => {
      panel.classList.toggle('hidden');
      btn.textContent = panel.classList.contains('hidden') ? 'Show JSON' : 'Hide JSON';
    });
  }
  ensureJsonOverlay();

  const API_KEY =
    (window.API_KEY && String(window.API_KEY)) ||
    (bodyEl.dataset.apiKey && String(bodyEl.dataset.apiKey)) ||
    "demo_123";

  // Removed legacy palette helpers and theme class management (unused)

  // Universal sandbox renderer only
  const RENDERERS = {
    custom(el, props) {
      const rawHtml = typeof props?.html === 'string' ? props.html : '';
      const html = stripExternalScripts(rawHtml);
      el.innerHTML = '';
      renderFullPage(html);
    }
  };


  function getRenderer(type) {
    const t = String(type || "").toLowerCase();
    if (t === 'custom') return RENDERERS.custom;
    return RENDERERS.custom;
  }

  function enterSite(doc) {
    if (doc && typeof doc.error === 'string') {
      return showError(doc.error);
    }
    if (doc && doc.kind === 'full_page_html' && typeof doc.html === 'string' && doc.html.trim()) {
      renderFullPage(doc.html);
      return;
    }
    const comps = Array.isArray(doc?.components) ? doc.components : [];
    const first = comps.find(c => c && typeof c === 'object' && c.props && (typeof c.props.html === 'string' && c.props.html.trim()));
    if (!first) return showError('No renderable HTML found');
    const type = normalizeType(first.type || 'custom');
    const props = { ...first.props };
    const container = document.createElement('div');
    container.className = 'mx-auto max-w-4xl px-4 py-6';
    const fn = getRenderer(type);
    const el = document.createElement('div');
    el.className = 'w-full';
    fn(el, props);
    container.appendChild(el);
    mainEl.innerHTML = '';
    mainEl.appendChild(container);
  }

  // Status UI was removed previously

  async function callGenerate(brief, seed) {
    const resp = await fetch("/generate", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": API_KEY,
      },
      body: JSON.stringify({ brief, seed }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      return { error: `Generate failed (${resp.status}): ${text || resp.statusText}` };
    }
    return resp.json();
  }

  // Ensure exactly one interactive widget exists in the page object.
  // Removed client-side widget synthesis; rely solely on server/LLM

  function setGenerating(is) {
    const btns = [landingBtn, document.getElementById('floatingGenerate')].filter(Boolean);
    btns.forEach(b => { if (!b) return; if (is) { b.setAttribute('aria-busy','true'); b.disabled=true; } else { b.removeAttribute('aria-busy'); b.disabled=false; } });
  }

  async function generateNew(e) {
    if (e) e.preventDefault();
    const brief = '';
    const seed = Math.floor(Math.random() * 1e9);
    const jsonOut = document.getElementById('jsonOut');
    if (jsonOut) jsonOut.textContent = '';
    setGenerating(true);
    showSpinner('Conjuring a new site…');
    const panel = document.getElementById('jsonPanel');
    const btn = document.getElementById('toggleJsonBtn');
    if (panel && !panel.classList.contains('hidden')) { panel.classList.add('hidden'); if (btn) btn.textContent = 'Show JSON'; }
    try {
    const doc = await callGenerate(brief, seed);
    enterSite(doc);
    if (jsonOut) jsonOut.textContent = JSON.stringify(doc, null, 2);
      ensureFloatingGenerate();
    } catch (err) {
      console.error('Generate error:', err);
    } finally {
      hideSpinner();
      setGenerating(false);
    }
  }

  function ensureFloatingGenerate() {
    // Remove landing button if I show floating button
    if (!document.getElementById('floatingGenerate')) {
      const wrap = document.createElement('div');
      wrap.className = 'fixed left-1/2 -translate-x-1/2 bottom-6 z-50';
      wrap.innerHTML = `<button id="floatingGenerate" type="button" class="px-5 py-3 rounded-full bg-indigo-600 text-white font-semibold shadow-lg hover:bg-indigo-700">Generate</button>`;
      document.body.appendChild(wrap);
      const btn = document.getElementById('floatingGenerate');
      if (btn) btn.addEventListener('click', generateNew);
    }
  }

  function renderLanding() {
    const lb = document.getElementById('landingGenerate');
    if (lb) lb.addEventListener('click', generateNew);
  }

  ensureFloatingGenerate();
  renderLanding();

  // Global counter: fetch and render "Sites generated: N" on load and after generation
  function ensureSitesCounterOverlay() {
    if (document.getElementById('sitesCounterFloating')) return;
    const wrap = document.createElement('div');
    wrap.id = 'sitesCounterFloating';
    wrap.className = 'fixed right-3 top-16 z-50';
    wrap.innerHTML = `
      <div id="sitesCounterBadge" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs shadow border border-slate-700/50">
        Sites generated: 0
      </div>`;
    document.body.appendChild(wrap);
  }

  ensureSitesCounterOverlay();

  async function refreshSitesCounter() {
    try {
      const el = document.getElementById('sitesCounter');
      const badge = document.getElementById('sitesCounterBadge');
      const resp = await fetch('/metrics/total', { headers: { 'accept': 'application/json' } });
      if (!resp.ok) throw new Error(String(resp.status));
      const data = await resp.json();
      const n = typeof data?.total === 'number' ? data.total : 0;
      if (el) el.textContent = `Sites generated: ${n}`;
      if (badge) badge.textContent = `Sites generated: ${n}`;
    } catch (e) {
    }
  }
  refreshSitesCounter();

  const _origEnterSite = enterSite;
  enterSite = function(doc){
    _origEnterSite(doc);
    if (doc && !doc.error) {
      refreshSitesCounter();
    }
  };

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  // Removed sanitize/format helpers (unused)

  function stripExternalScripts(html) {
    // Remove <script src="..."> tags, keep inline scripts
    return String(html).replace(/<script[^>]*\bsrc\s*=\s*['"][^'"]+['"][^>]*>\s*<\/script>/gi, '');
  }

  // Removed sandbox iframe builder (unused after full-page rendering switch)

  // New: render full-page HTML into the document, execute inline scripts, and adopt styles/background
  function renderFullPage(html) {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(String(html), 'text/html');
      document.querySelectorAll('style[data-gen-style="1"]').forEach(s => s.remove());
      doc.head && doc.head.querySelectorAll('style').forEach(s => {
        const st = document.createElement('style');
        st.setAttribute('data-gen-style','1');
        st.textContent = s.textContent || '';
        document.head.appendChild(st);
      });
      if (doc.body) {
        if (doc.body.getAttribute('style')) {
          document.body.setAttribute('style', doc.body.getAttribute('style'));
        }
        if (doc.body.getAttribute('class')) {
          document.body.setAttribute('class', doc.body.getAttribute('class'));
        }
      }
      // Replace main content area with generated body children
      mainEl.innerHTML = '';
      const frag = document.createDocumentFragment();
      const nodes = (doc.body && doc.body.childNodes) ? Array.from(doc.body.childNodes) : [];
      nodes.forEach(n => frag.appendChild(n.cloneNode(true)));
      mainEl.appendChild(frag);
      const scripts = [];
      if (doc.head) scripts.push(...doc.head.querySelectorAll('script'));
      if (doc.body) scripts.push(...doc.body.querySelectorAll('script'));
      scripts.forEach(old => {
        const hasSrc = old.hasAttribute('src');
        if (hasSrc) return;
        const sc = document.createElement('script');
        if (old.type) sc.type = old.type;
        sc.textContent = old.textContent || '';
        mainEl.appendChild(sc);
      });
      ensureFloatingGenerate();
      ensureSitesCounterOverlay();
    } catch (e) {
      console.error('Full-page render error:', e);
      showError('Failed to render content.');
    }
  }

  function showError(msg) {
    const wrap = document.createElement('div');
    wrap.className = 'max-w-xl mx-auto mt-8 px-4';
    wrap.innerHTML = `<div class="p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">${escapeHtml(String(msg||'Error'))}</div>`;
    mainEl.innerHTML = '';
    mainEl.appendChild(wrap);
  }

  function normalizeType(t) {
    return String(t || "").toLowerCase().replaceAll("-", "_");
  }

  // Removed paletteHex utility (unused)

  function ensureSpinner() {
    let el = document.getElementById("gen-spinner");
    if (!el) {
      el = document.createElement("div");
      el.id = "gen-spinner";
      el.className = "hidden fixed inset-0 grid place-items-center bg-black/40 z-50";
      el.innerHTML = `
        <div class="flex flex-col items-center gap-3 text-white">
          <div class="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent"></div>
          <div id="spinnerMsg" class="text-sm">Generating…</div>
        </div>`;
      document.body.appendChild(el);
    }
    return el;
  }
  function showSpinner(msg) { const el = ensureSpinner(); const m = document.getElementById('spinnerMsg'); if (m && msg) m.textContent = msg; el.classList.remove("hidden"); }
  function hideSpinner() { ensureSpinner().classList.add("hidden"); }
})();
