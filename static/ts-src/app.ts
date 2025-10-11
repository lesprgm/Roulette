// Migrated TypeScript version of app.js (core client logic)
// NDW runtime is loaded separately via a plain <script src="/static/ts-build/ndw.js"></script>
// I intentionally do NOT import './ndw' so this compiles to a classic script (no type="module").
// Provide an empty export so this file is treated as a module and allows scoped types without polluting global.
export {};

interface NdwBackground { style?:string; class?:string }
interface NdwSnippet { kind:'ndw_snippet_v1'; title?:string; html?:string; css?:string; js?:string; background?:NdwBackground }
interface FullPageDoc { kind:'full_page_html'; html:string }
interface ErrorDoc { error:string }
interface ComponentDoc { components: any[] }
type AppNormalizedDoc = NdwSnippet | FullPageDoc | ErrorDoc | ComponentDoc | any;

type AppWindow = Window & { __NDW_showSnippetErrorOverlay?: (err:any)=>void; API_KEY?:string };
const _w = window as AppWindow;

const bodyEl = document.body;
const mainEl = document.getElementById('appMain');
console.debug('[ndw] app script evaluated; readyState=', document.readyState);

function ensureScrollableBody(){
  try {
    document.documentElement.style.overflowX = 'auto';
    document.documentElement.style.overflowY = 'auto';
    document.body.style.overflowX = 'auto';
    document.body.style.overflowY = 'auto';
    document.body.style.removeProperty('overscroll-behavior');
    document.documentElement.style.removeProperty('overscroll-behavior');
    const removable = ['overflow-hidden','no-scroll','lock-scroll'];
    removable.forEach(cls=>{
      if (document.body.classList.contains(cls)) document.body.classList.remove(cls);
      if (document.documentElement.classList.contains(cls)) document.documentElement.classList.remove(cls);
    });
  } catch(err){ console.warn('ensureScrollableBody failed', err); }
}

function ensureJsonOverlay(){
  if (document.getElementById('jsonOverlay')) return;
  const wrap = document.createElement('div');
  wrap.id='jsonOverlay';
  wrap.className='fixed top-3 right-3 z-50';
  wrap.innerHTML=`<button id="toggleJsonBtn" type="button" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs">Show JSON</button>
  <div id="jsonPanel" class="hidden mt-2 max-w-[60vw] max-h-[60vh] overflow-auto bg-white border border-slate-200 rounded shadow-lg p-3 text-slate-900">
    <pre id="jsonOut" class="text-[11px] whitespace-pre-wrap text-slate-900"></pre>
  </div>`;
  document.body.appendChild(wrap);
  const btn = document.getElementById('toggleJsonBtn') as HTMLButtonElement | null;
  const panel = document.getElementById('jsonPanel');
  if (btn && panel){
    btn.addEventListener('click', ()=>{
      panel.classList.toggle('hidden');
      btn.textContent = panel.classList.contains('hidden') ? 'Show JSON' : 'Hide JSON';
    });
  }
}
ensureJsonOverlay();

const API_KEY = (_w.API_KEY && String(_w.API_KEY)) || (bodyEl.dataset.apiKey && String(bodyEl.dataset.apiKey)) || 'demo_123';

function stripExternalScripts(html:string){
  return String(html).replace(/<script[^>]*\bsrc\s*=\s*['"][^'"]+['"][^>]*>\s*<\/script>/gi, '');
}

function enterSite(doc: AppNormalizedDoc){
  const anyDoc:any = doc;
  if (anyDoc && typeof anyDoc.error === 'string') return showError(anyDoc.error);
  if (anyDoc && anyDoc.kind === 'ndw_snippet_v1') return renderNdwSnippet(anyDoc as NdwSnippet);
  if (anyDoc && anyDoc.kind === 'full_page_html' && typeof anyDoc.html === 'string' && anyDoc.html.trim()) return renderFullPage(anyDoc.html);
  const comps = Array.isArray(anyDoc?.components) ? anyDoc.components : [];
  const first = comps.find((c:any)=> c && c.props && typeof c.props.html === 'string' && c.props.html.trim());
  if (!first) return showError('No renderable HTML found');
  renderInline(first.props.html);
}

async function callGenerate(brief:string, seed:number){
  const resp = await fetch('/generate', { method:'POST', headers:{'content-type':'application/json','x-api-key':API_KEY}, body: JSON.stringify({ brief, seed }) });
  if (!resp.ok){
    const text = await resp.text();
    return { error: `Generate failed (${resp.status}): ${text || resp.statusText}` };
  }
  return resp.json();
}

function setGenerating(is:boolean){
  const coreBtns = [document.getElementById('landingGenerate'), document.getElementById('floatingGenerate')].filter(Boolean) as HTMLElement[];
  const inlineBtns = Array.from(document.querySelectorAll('[data-gen-button="1"]')) as HTMLElement[];
  [...coreBtns, ...inlineBtns].forEach(b=>{ if (is){ b.setAttribute('aria-busy','true'); (b as any).disabled = true; } else { b.removeAttribute('aria-busy'); (b as any).disabled = false; } });
}

(_w as any).ndwGenerate = generateNew;
async function generateNew(e?:Event){
  console.debug('[ndw] generateNew invoked');
  if (e) e.preventDefault();
  const seed = Math.floor(Math.random()*1e9);
  const jsonOut = document.getElementById('jsonOut');
  if (jsonOut) jsonOut.textContent='';
  setGenerating(true); showSpinner('Just a moment…');
  const panel = document.getElementById('jsonPanel');
  const btn = document.getElementById('toggleJsonBtn');
  if (panel && !panel.classList.contains('hidden')) { panel.classList.add('hidden'); if(btn) btn.textContent='Show JSON'; }
  try {
    const doc = await callGenerate('', seed);
    enterSite(doc);
    if (jsonOut) jsonOut.textContent = JSON.stringify(doc, null, 2);
    ensureFloatingGenerate(); adaptGenerateButtons();
  } catch(err){ console.error('Generate error:', err); }
  finally { hideSpinner(); setGenerating(false); }
}

function ensureFloatingGenerate(){
  console.debug('[ndw] ensureFloatingGenerate called');
  const existing = document.getElementById('floatingGenerateWrap');
  if (existing) existing.remove(); else {
    const oldBtn = document.getElementById('floatingGenerate');
    if (oldBtn){ const parent = oldBtn.closest('#floatingGenerateWrap') || oldBtn.parentElement || oldBtn; try { parent.remove(); } catch(_) {} }
  }
  const wrap = document.createElement('div');
  wrap.id='floatingGenerateWrap'; wrap.className='fixed left-1/2 -translate-x-1/2 bottom-6 z-50';
  wrap.innerHTML=`<div class="ndw-button button" aria-label="Generate"><button id="floatingGenerate" name="checkbox" type="button" aria-label="Generate"></button><span></span><span></span><span></span><span></span></div>`;
  document.body.appendChild(wrap);
  document.getElementById('floatingGenerate')?.addEventListener('click', generateNew);
}
ensureFloatingGenerate();

function renderLanding(){
  const btn = document.getElementById('landingGenerate');
  if (!btn) return;
  if ((btn as any).__ndwBound) return;
  btn.addEventListener('click', generateNew);
  (btn as any).__ndwBound = true;
  console.debug('[ndw] landingGenerate bound');
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', ()=>{ console.debug('[ndw] DOMContentLoaded'); renderLanding(); });
} else {
  renderLanding();
}

function ensureSitesCounterOverlay(){
  if (document.getElementById('sitesCounterFloating')) return;
  const wrap = document.createElement('div');
  wrap.id='sitesCounterFloating'; wrap.className='fixed right-3 top-16 z-50';
  wrap.innerHTML=`<div id="sitesCounterBadge" class="px-3 py-2 rounded bg-slate-900/80 text-white text-xs shadow border border-slate-700/50">Sites generated: 0</div>`;
  document.body.appendChild(wrap);
}
ensureSitesCounterOverlay();

async function refreshSitesCounter(){
  try {
    const el = document.getElementById('sitesCounter');
    const badge = document.getElementById('sitesCounterBadge');
    const resp = await fetch('/metrics/total', { headers:{accept:'application/json'} });
    if (!resp.ok) throw new Error(String(resp.status));
    const data = await resp.json();
    const n = typeof data?.total === 'number' ? data.total : 0;
    if (el) el.textContent = `Sites generated: ${n}`;
    if (badge) badge.textContent = `Sites generated: ${n}`;
  } catch{}
}
refreshSitesCounter();

// Small UI helper to show or remove a snippet title overlay.
function upsertTitleOverlay(title?: string){
  const id = 'ndw-title';
  let el = document.getElementById(id) as HTMLDivElement | null;
  if (!title){
    if (el && el.parentNode) el.parentNode.removeChild(el);
    return;
  }
  if (!el){
    el = document.createElement('div');
    el.id = id;
    el.style.cssText = 'position:fixed;z-index:9998;top:10px;left:10px;padding:6px 10px;border-radius:8px;background:rgba(0,0,0,.4);backdrop-filter:saturate(120%) blur(2px);color:#fff;font:600 12px/1.2 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;pointer-events:none;max-width:60vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
    document.body.appendChild(el);
  }
  el.textContent = String(title || '').trim();
}

function escapeHtml(s:string){ return s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); }

function renderFullPage(html:string){
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(String(html), 'text/html');
    document.querySelectorAll('style[data-gen-style="1"]').forEach(s=>s.remove());
    doc.head?.querySelectorAll('style').forEach(s=>{ const st=document.createElement('style'); st.setAttribute('data-gen-style','1'); st.textContent=s.textContent||''; document.head.appendChild(st); });
    document.body.removeAttribute('style'); document.body.className='';
    if (doc.body){
      const newStyle = doc.body.getAttribute('style');
      const newClass = doc.body.getAttribute('class');
      if (newStyle) document.body.setAttribute('style', newStyle);
      if (newClass) document.body.setAttribute('class', newClass);
    }
    if (mainEl){
      mainEl.innerHTML='';
      const frag=document.createDocumentFragment();
      const nodes = doc.body? Array.from(doc.body.childNodes):[];
      nodes.forEach(n=>frag.appendChild(n.cloneNode(true)));
      mainEl.appendChild(frag);
    }
    const scripts: HTMLScriptElement[] = [];
    if (doc.head) scripts.push(...Array.from(doc.head.querySelectorAll('script')));
    if (doc.body) scripts.push(...Array.from(doc.body.querySelectorAll('script')));
    scripts.forEach(old=>{ if(old.src) return; const sc=document.createElement('script'); if (old.type) sc.type=old.type; sc.textContent=old.textContent||''; mainEl?.appendChild(sc); });
    ensureFloatingGenerate(); ensureSitesCounterOverlay(); adaptGenerateButtons();
    ensureScrollableBody();
    upsertTitleOverlay(undefined);
  } catch(e){ console.error('Full-page render error:', e); showError('Failed to render content.'); }
}

function renderInline(html:string){
  try {
    const parser=new DOMParser();
    const doc=parser.parseFromString(String(html),'text/html');
    doc.head?.querySelectorAll('style').forEach(s=>{ const st=document.createElement('style'); st.setAttribute('data-gen-style','1'); st.textContent=s.textContent||''; document.head.appendChild(st); });
    if (mainEl){
      mainEl.innerHTML='';
      const frag=document.createDocumentFragment();
      const nodes=doc.body?Array.from(doc.body.childNodes):[];
      nodes.forEach(n=>frag.appendChild(n.cloneNode(true)));
      mainEl.appendChild(frag);
    }
    const scripts:HTMLScriptElement[]=[];
    if (doc.head) scripts.push(...Array.from(doc.head.querySelectorAll('script')));
    if (doc.body) scripts.push(...Array.from(doc.body.querySelectorAll('script')));
    scripts.forEach(old=>{ if(old.src) return; const sc=document.createElement('script'); if(old.type) sc.type=old.type; sc.textContent=old.textContent||''; mainEl?.appendChild(sc); });
    ensureFloatingGenerate(); ensureSitesCounterOverlay(); adaptGenerateButtons();
    ensureScrollableBody();
    upsertTitleOverlay(undefined);
  } catch(e){ console.error('Inline render error:', e); showError('Failed to render content.'); }
}

function renderNdwSnippet(snippet:NdwSnippet){
  try {
  const bg = snippet.background || {};
  const hasBg = (typeof bg.style === 'string' && bg.style.trim()) || (typeof bg.class === 'string' && bg.class.trim());
  // Apply background first to avoid any white flash behind canvas
  document.body.removeAttribute('style'); document.body.className='';
  if (hasBg){ if (bg.style) document.body.setAttribute('style',bg.style); if (bg.class) document.body.setAttribute('class',bg.class); }
    document.querySelectorAll('style[data-ndw-snippet="1"]').forEach(s=>s.remove());
    if (snippet.css && snippet.css.trim()){ const st=document.createElement('style'); st.setAttribute('data-ndw-snippet','1'); st.textContent=snippet.css; document.head.appendChild(st); }
    if (mainEl){
      mainEl.innerHTML='';
      const wrap=document.createElement('div'); wrap.id='ndw-app';
      const html = snippet.html || '';
      const safeHtml = stripExternalScripts(html);
      const hasCanvasCreation = /NDW\.makeCanvas/.test(snippet.js || '');
      
      if (safeHtml.trim()) {
        wrap.innerHTML = safeHtml;
      } else if (!hasCanvasCreation) {
        // Only create fallback canvas if snippet doesn't call NDW.makeCanvas
        const c = document.createElement('canvas');
        c.id = 'canvas';
        c.style.display = 'block';
        c.style.width = '100vw';
        c.style.height = '100vh';
        wrap.appendChild(c);
      }
      // else: snippet has no HTML but calls makeCanvas; leave wrap empty, JS will populate
      const innerApp = wrap.querySelector('#ndw-app');
      if (innerApp && innerApp !== wrap){
        const cls = innerApp.getAttribute('class'); const sty = innerApp.getAttribute('style');
        if (cls) wrap.className = `${wrap.className} ${cls}`.trim();
        if (sty) wrap.setAttribute('style', `${wrap.getAttribute('style')||''}; ${sty}`.trim());
        const kids = Array.from(innerApp.childNodes); innerApp.remove(); kids.forEach(n=>wrap.appendChild(n));
      }
      mainEl.appendChild(wrap);
    }
    upsertTitleOverlay(snippet.title);
    if (snippet.js && snippet.js.trim()){
      if (!_w.NDW) console.warn('NDW runtime not found; snippet JS may fail.');
      if (!_w.__NDW_showSnippetErrorOverlay){
        _w.__NDW_showSnippetErrorOverlay = (err:any)=>{
          try { let el = document.getElementById('ndwSnippetError'); if (!el){ el=document.createElement('div'); el.id='ndwSnippetError'; Object.assign(el.style,{position:'fixed',top:'12px',left:'12px',zIndex:'1000',background:'rgba(220,38,38,0.95)',color:'#fff',padding:'10px 12px',borderRadius:'8px',font:'12px/1.4 system-ui, sans-serif',boxShadow:'0 6px 20px rgba(0,0,0,0.25)',maxWidth:'60vw'}); el.innerHTML='<strong>Snippet error</strong><div id="ndwSnippetErrorMsg" style="margin-top:6px;white-space:pre-wrap"></div>'; document.body.appendChild(el);} const msg = document.getElementById('ndwSnippetErrorMsg'); if(msg) msg.textContent = String(err && (err.message||err)).slice(0,500); } catch(e){ console.error('Snippet error overlay failure', e); }
        };
      }
      const sc = document.createElement('script'); sc.type='text/javascript'; sc.textContent=`(function(){try\n{${snippet.js}\n}catch(err){try{(window.__NDW_showSnippetErrorOverlay||console.error).call(window,err);}catch(_){console.error(err);}}})();`;
      document.body.appendChild(sc);
    }
    ensureFloatingGenerate(); ensureSitesCounterOverlay(); adaptGenerateButtons();
    ensureScrollableBody();
  } catch(e){ console.error('NDW snippet render error:', e); showError('Failed to render snippet.'); }
}

function showError(msg:string){ if (!mainEl) return; const wrap=document.createElement('div'); wrap.className='max-w-xl mx-auto mt-8 px-4'; wrap.innerHTML=`<div class="p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">${escapeHtml(String(msg||'Error'))}</div>`; mainEl.innerHTML=''; mainEl.appendChild(wrap); }

let __genBtnSeq = 0;
function buildUiverseButton(id?:string){ const wrap=document.createElement('div'); wrap.className='inline-block align-middle'; wrap.innerHTML=`<div class="ndw-button button" aria-label="Generate"><button ${id?`id="${id}"`:''} data-gen-button="1" name="checkbox" type="button" aria-label="Generate"></button><span></span><span></span><span></span><span></span></div>`; return wrap; }

function looksLikeGenerate(el:HTMLElement){
  const label = (el.getAttribute('aria-label') || el.textContent || '').trim().toLowerCase();
  const id = (el.id || '').toLowerCase();
  const cls = (el.className || '').toLowerCase();
  if (id === 'landinggenerate' || id === 'floatinggenerate') return false;
  if (el.closest('.button')) return false;
  return label === 'generate' || /\bgenerate\b/.test(label) || /\bgenerate\b/.test(id) || /\bgenerate\b/.test(cls);
}

function adaptGenerateButtons(){
  const scope = mainEl || document;
  const candidates = Array.from(scope.querySelectorAll('button, a[role="button"], a[href="#generate"], input[type="button"], input[type="submit"]')) as HTMLElement[];
  candidates.forEach(el=>{
    if (!looksLikeGenerate(el)) return;
    const newId = `inlineGenerate_${++__genBtnSeq}`;
    const comp = buildUiverseButton(newId);
    comp.style.display = getComputedStyle(el).display === 'block' ? 'block' : 'inline-block';
    el.replaceWith(comp);
    const btn = comp.querySelector('button');
    btn?.addEventListener('click', generateNew);
  });
}

function ensureSpinner(){
  let el = document.getElementById('gen-spinner');
  if (!el){ el = document.createElement('div'); el.id='gen-spinner'; el.className='hidden fixed inset-0 grid place-items-center bg-black/40 z-50'; el.innerHTML=`<div class="flex flex-col items-center gap-3 text-white"><div class="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent"></div><div id="spinnerMsg" class="text-sm">Generating…</div></div>`; document.body.appendChild(el); }
  return el;
}
function showSpinner(msg?:string){ const el=ensureSpinner(); const m=document.getElementById('spinnerMsg'); if (m && msg) m.textContent=msg; el.classList.remove('hidden'); }
function hideSpinner(){ ensureSpinner().classList.add('hidden'); }

const _origEnterSite = enterSite;
function enterSiteWithCounter(doc:any){ _origEnterSite(doc); if (doc && !doc.error) refreshSitesCounter(); }
// @ts-ignore
enterSite = enterSiteWithCounter;
