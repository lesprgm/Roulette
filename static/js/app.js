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

  const DEFAULT_COLORS = { primary: "slate", accent: "indigo" };
  const COLOR_CLASSES = {
    primary: {
      // six-color set (supported by server prompt)
      slate:   { sectionBg: "bg-slate-900",   sectionText: "text-white", muted: "text-slate-300" },
      indigo:  { sectionBg: "bg-indigo-700",  sectionText: "text-white", muted: "text-slate-200" },
      rose:    { sectionBg: "bg-rose-700",    sectionText: "text-white", muted: "text-slate-200" },
      emerald: { sectionBg: "bg-emerald-700", sectionText: "text-white", muted: "text-slate-200" },
      amber:   { sectionBg: "bg-amber-600",   sectionText: "text-slate-900", muted: "text-slate-700" },
      violet:  { sectionBg: "bg-violet-700",  sectionText: "text-white", muted: "text-slate-200" },
      // legacy fallbacks (harmless if server returns older palettes)
      gray:    { sectionBg: "bg-gray-900",    sectionText: "text-white", muted: "text-gray-300" },
      stone:   { sectionBg: "bg-stone-900",   sectionText: "text-white", muted: "text-stone-300" },
      zinc:    { sectionBg: "bg-zinc-900",    sectionText: "text-white", muted: "text-zinc-300" },
      neutral: { sectionBg: "bg-neutral-900", sectionText: "text-white", muted: "text-neutral-300" },
    },
    accent: {
      indigo:  { btn: "bg-indigo-600 hover:bg-indigo-700",  text: "text-indigo-600" },
      violet:  { btn: "bg-violet-600 hover:bg-violet-700",  text: "text-violet-600" },
      emerald: { btn: "bg-emerald-600 hover:bg-emerald-700",text: "text-emerald-600" },
      amber:   { btn: "bg-amber-500 hover:bg-amber-600",    text: "text-amber-600" },
      rose:    { btn: "bg-rose-600 hover:bg-rose-700",      text: "text-rose-600" },
      // legacy
      sky:     { btn: "bg-sky-600 hover:bg-sky-700",        text: "text-sky-600" },
    },
  };
  function resolveColors(palette) {
    const p = (palette?.primary || DEFAULT_COLORS.primary);
    const a = (palette?.accent || DEFAULT_COLORS.accent);
    const P = COLOR_CLASSES.primary[p] || COLOR_CLASSES.primary[DEFAULT_COLORS.primary];
    const A = COLOR_CLASSES.accent[a] || COLOR_CLASSES.accent[DEFAULT_COLORS.accent];
    return { primary: P, accent: A };
  }

  // Visible palette map for obvious variety across pages
  const PALETTES = {
    slate:  { bg: 'bg-slate-900',  text: 'text-slate-100', card: 'border-slate-300',  accentBtn: 'bg-slate-900 hover:bg-slate-800',   accentText: 'text-slate-100' },
    indigo: { bg: 'bg-indigo-700', text: 'text-white',     card: 'border-indigo-200', accentBtn: 'bg-indigo-600 hover:bg-indigo-700', accentText: 'text-white' },
    rose:   { bg: 'bg-rose-700',   text: 'text-white',     card: 'border-rose-200',   accentBtn: 'bg-rose-600 hover:bg-rose-700',   accentText: 'text-white' },
    emerald:{ bg: 'bg-emerald-700',text: 'text-white',     card: 'border-emerald-200',accentBtn: 'bg-emerald-600 hover:bg-emerald-700',accentText: 'text-white' },
    amber:  { bg: 'bg-amber-500',  text: 'text-slate-900', card: 'border-amber-300',  accentBtn: 'bg-amber-600 hover:bg-amber-700', accentText: 'text-slate-900' },
    violet: { bg: 'bg-violet-700', text: 'text-white',     card: 'border-violet-200', accentBtn: 'bg-violet-600 hover:bg-violet-700',accentText: 'text-white' },
    cyan:   { bg: 'bg-cyan-600',   text: 'text-white',     card: 'border-cyan-200',   accentBtn: 'bg-cyan-600 hover:bg-cyan-700',   accentText: 'text-white' },
  };

  // Known theme class sets to clean before applying a new palette
  const HERO_BG_CLASSES = ['bg-slate-900','bg-indigo-700','bg-rose-700','bg-emerald-700','bg-amber-500','bg-violet-700','bg-cyan-600'];
  const HERO_TEXT_CLASSES = ['text-white','text-slate-100','text-slate-900'];
  const CTA_BG_CLASSES = [
    'bg-indigo-600','hover:bg-indigo-700',
    'bg-violet-600','hover:bg-violet-700',
    'bg-emerald-600','hover:bg-emerald-700',
    'bg-amber-600','hover:bg-amber-700',
    'bg-rose-600','hover:bg-rose-700',
    'bg-slate-900','hover:bg-slate-800',
    'bg-cyan-600','hover:bg-cyan-700',
    'bg-sky-600','hover:bg-sky-700'
  ];
  const CTA_TEXT_CLASSES = ['text-white','text-slate-100','text-slate-900'];
  const CARD_BORDER_CLASSES = ['border-slate-300','border-indigo-200','border-rose-200','border-emerald-200','border-amber-300','border-violet-200','border-cyan-200'];

  function removeClasses(el, classes) {
    classes.forEach(cls => el.classList.remove(cls));
  }

  function randomizePaletteIfMissing(palette) {
    const primaries = ['violet','emerald','rose','amber','indigo','cyan','slate'];
    const accents = ['indigo','violet','emerald','amber','rose','cyan','slate'];
    return {
      primary: palette?.primary || primaries[Math.floor(Math.random()*primaries.length)],
      accent: palette?.accent || accents[Math.floor(Math.random()*accents.length)],
    };
  }

  function applyPalette(palette) {
    const pfix = randomizePaletteIfMissing(palette);
    const p = (pfix.primary && PALETTES[pfix.primary]) ? pfix.primary : 'slate';
    const pal = PALETTES[p];
    // Theme top-level hero/cta/cards and add a clear theme class on body
    bodyEl.classList.remove('theme-slate','theme-indigo','theme-rose','theme-emerald','theme-amber','theme-violet','theme-cyan');
    bodyEl.classList.add(`theme-${p}`);
    document.querySelectorAll('[data-role="hero"]').forEach((el) => { removeClasses(el, HERO_BG_CLASSES); removeClasses(el, HERO_TEXT_CLASSES); el.classList.add(pal.bg, pal.text); });
    document.querySelectorAll('[data-role="cta-btn"]').forEach((el) => { removeClasses(el, CTA_BG_CLASSES); removeClasses(el, CTA_TEXT_CLASSES); el.classList.add(...pal.accentBtn.split(' '), pal.accentText); });
    document.querySelectorAll('[data-role="card"]').forEach((el) => { removeClasses(el, CARD_BORDER_CLASSES); el.classList.add(pal.card); });
  }

  const RENDERERS = {
  widget(el, props, colors) {
      const kind = String(props?.kind || 'click_counter').toLowerCase();
      const title = props?.title || {
        click_counter: 'Click Counter',
        dont_press: "Don't Press",
        compliment_generator: 'Compliment Generator',
        color_party: 'Color Party',
        emoji_rain: 'Emoji Rain',
        pixel_painter: 'Pixel Painter',
        yes_or_no: 'Yes or No',
        coin_flip: 'Coin Flip',
        guess_number: 'Guess the Number',
        tic_tac_toe: 'Tic Tac Toe',
      }[kind] || 'Widget';

      // Utility: random helpers
      const randItem = (arr) => arr[Math.floor(Math.random() * arr.length)];
      const mkSection = (inner) => `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          <h3 class="text-xl font-semibold">${escapeHtml(title)}</h3>
          <div class="mt-3">${inner}</div>
        </section>`;

      const compliments = props?.compliments && Array.isArray(props.compliments) && props.compliments.length
        ? props.compliments
        : ['You look great today!', 'You write delightful code!', 'That was a smart click!', 'A+ taste in palettes.', 'You make bugs disappear.'];

      switch (kind) {
        case 'click_counter': {
          el.innerHTML = mkSection(`
            <div class="flex items-center gap-4">
              <div class="text-3xl font-extrabold" id="ccount">0</div>
              <button type="button" class="px-4 py-2 rounded text-white" data-role="cta-btn" id="cbtn">Click me</button>
            </div>`);
          const c = el.querySelector('#ccount');
          const b = el.querySelector('#cbtn');
          let n = 0; b.addEventListener('click', () => { n++; c.textContent = String(n); });
          break;
        }
        case 'dont_press': {
          el.innerHTML = mkSection(`
            <button type="button" class="px-4 py-3 rounded bg-rose-600 text-white hover:bg-rose-700" id="dbtn">Do NOT press</button>
            <div class="mt-3 text-sm text-slate-700" id="dmsg"></div>`);
          const b = el.querySelector('#dbtn');
          const m = el.querySelector('#dmsg');
          let n = 0;
          b.addEventListener('click', () => { n++; m.textContent = `I told you not to! (${n})`; });
          break;
        }
        case 'compliment_generator': {
          el.innerHTML = mkSection(`
            <div class="flex items-center gap-3">
              <button type="button" class="px-4 py-2 rounded text-white" data-role="cta-btn" id="gbtn">Compliment me</button>
              <div class="text-sm text-slate-700" id="gout">Click for a compliment ✨</div>
            </div>`);
          const b = el.querySelector('#gbtn');
          const o = el.querySelector('#gout');
          b.addEventListener('click', () => { o.textContent = randItem(compliments); });
          break;
        }
        case 'color_party': {
          el.innerHTML = mkSection(`
            <div class="h-24 rounded border border-slate-200" id="cbox"></div>
            <button type="button" class="mt-3 px-4 py-2 rounded text-white" data-role="cta-btn" id="pbtn">Party 🎉</button>`);
          const box = el.querySelector('#cbox');
          const b = el.querySelector('#pbtn');
          const randColor = () => `hsl(${Math.floor(Math.random()*360)}, 85%, 60%)`;
          box.style.background = randColor();
          b.addEventListener('click', () => { box.style.background = randColor(); });
          break;
        }
        case 'emoji_rain': {
          el.innerHTML = mkSection(`
            <div class="relative h-32 overflow-hidden rounded border border-slate-200 bg-white" id="er"></div>
            <button type="button" class="mt-3 px-4 py-2 rounded text-white" data-role="cta-btn" id="ebtn">Make it rain 🌧️</button>`);
          const area = el.querySelector('#er');
          const b = el.querySelector('#ebtn');
          const pool = props?.emojis && Array.isArray(props.emojis) && props.emojis.length ? props.emojis : ['✨','🎈','🎉','🌟','💫','🔥','🍀','🌈','🪄'];
          b.addEventListener('click', () => {
            for (let i=0;i<12;i++) {
              const span = document.createElement('span');
              span.textContent = randItem(pool);
              span.className = 'absolute text-2xl select-none transition-all duration-700';
              span.style.left = Math.floor(Math.random()*90)+'%';
              span.style.top = '-10%';
              area.appendChild(span);
              requestAnimationFrame(() => {
                span.style.top = '90%';
                span.style.opacity = '0';
              });
              setTimeout(() => span.remove(), 800);
            }
          });
          break;
        }
        case 'pixel_painter': {
          const size = Math.min(Math.max(parseInt(props?.size||'10',10)||10, 6), 16);
          const cells = size*size;
          const cellHtml = Array.from({length: cells}).map(() => '<div class="h-5 w-5 md:h-6 md:w-6 border border-slate-200 bg-white"></div>').join('');
          el.innerHTML = mkSection(`
            <div class="grid gap-0" style="grid-template-columns: repeat(${size}, minmax(0, 1fr));" id="grid">${cellHtml}</div>
            <div class="mt-2 text-xs text-slate-500">Click squares to paint. Click again to erase.</div>`);
          el.querySelectorAll('#grid > div').forEach((d) => {
            d.addEventListener('click', () => d.classList.toggle('bg-slate-900'));
          });
          break;
        }
        case 'yes_or_no': {
          el.innerHTML = mkSection(`
            <div class="flex items-center gap-3">
              <button type="button" class="px-4 py-2 rounded text-white ${colors.accent.btn}" data-role="cta-btn" id="ybtn">Ask</button>
              <div class="text-lg font-bold" id="yout">?</div>
            </div>`);
          const b = el.querySelector('#ybtn');
          const o = el.querySelector('#yout');
          b.addEventListener('click', () => { o.textContent = Math.random()<0.5 ? 'Yes' : 'No'; });
          break;
        }
        case 'coin_flip': {
          el.innerHTML = mkSection(`
            <div class="flex items-center gap-3">
              <button type="button" class="px-4 py-2 rounded text-white ${colors.accent.btn}" data-role="cta-btn" id="fbtn">Flip</button>
              <div class="text-lg font-bold" id="fout">—</div>
            </div>`);
          const b = el.querySelector('#fbtn');
          const o = el.querySelector('#fout');
          b.addEventListener('click', () => { o.textContent = Math.random()<0.5 ? 'Heads' : 'Tails'; });
          break;
        }
        case 'guess_number': {
          const max = Math.min(Math.max(parseInt(props?.max||'10',10)||10, 5), 50);
          const pick = () => Math.floor(Math.random()*max)+1;
          let secret = pick();
          el.innerHTML = mkSection(`
            <div class="flex items-center gap-2">
              <input type="number" min="1" max="${max}" class="w-24 px-2 py-1 rounded border border-slate-300" id="ginp" placeholder="1-${max}">
              <button type="button" class="px-3 py-1.5 rounded text-white" data-role="cta-btn" id="gbtn2">Guess</button>
            </div>
            <div class="mt-2 text-sm" id="gmsg">Pick a number between 1 and ${max}.</div>`);
          const inp = el.querySelector('#ginp');
          const b = el.querySelector('#gbtn2');
          const m = el.querySelector('#gmsg');
          b.addEventListener('click', () => {
            const val = parseInt(inp.value, 10);
            if (!val) { m.textContent = 'Enter a number.'; return; }
            if (val === secret) { m.textContent = 'Correct! New round…'; secret = pick(); inp.value=''; return; }
            m.textContent = val < secret ? 'Too low.' : 'Too high.';
          });
          break;
        }
        case 'tic_tac_toe': {
          const board = Array(9).fill('');
          let player = 'X';
          const winLines = [ [0,1,2],[3,4,5],[6,7,8], [0,3,6],[1,4,7],[2,5,8], [0,4,8],[2,4,6] ];
          const cell = (i) => `<button data-i="${i}" class="h-14 w-14 text-xl font-bold border border-slate-300">${board[i]}</button>`;
          el.innerHTML = mkSection(`
            <div class="grid grid-cols-3 gap-0 w-[216px]" id="ttt">${Array.from({length:9}).map((_,i)=>cell(i)).join('')}</div>
            <div class="mt-2 text-sm" id="tmsg">Player ${player}'s turn</div>
            <button type="button" class="mt-2 px-3 py-1.5 rounded text-white" data-role="cta-btn" id="treset">Reset</button>`);
          const root = el.querySelector('#ttt');
          const msg = el.querySelector('#tmsg');
          const reset = el.querySelector('#treset');
          const render = () => {
            root.querySelectorAll('button[data-i]').forEach((b,i)=>{ b.textContent = board[i]; b.disabled = !!board[i]; });
          };
          const winner = () => {
            for (const [a,b,c] of winLines) {
              if (board[a] && board[a]===board[b] && board[a]===board[c]) return board[a];
            }
            return board.every(Boolean) ? 'draw' : '';
          };
          root.addEventListener('click', (e)=>{
            const t = e.target; if (!(t instanceof HTMLElement)) return;
            const i = parseInt(t.getAttribute('data-i')||'-1',10); if (i<0 || board[i]) return;
            board[i] = player;
            const w = winner();
            if (w) {
              render();
              msg.textContent = w==='draw' ? 'Draw!' : `Player ${w} wins!`;
              root.querySelectorAll('button[data-i]').forEach(b=>b.disabled=true);
              return;
            }
            player = (player==='X') ? 'O' : 'X';
            render();
            msg.textContent = `Player ${player}'s turn`;
          });
          reset.addEventListener('click', ()=>{
            for (let i=0;i<9;i++) board[i]='';
            player='X';
            root.querySelectorAll('button[data-i]').forEach(b=>b.disabled=false);
            render();
            msg.textContent = `Player ${player}'s turn`;
          });
          render();
          break;
        }
        default: {
          // Unknown kind → show a small message, but keep layout consistent
          el.innerHTML = mkSection(`<div class="text-sm text-slate-600">Unknown widget kind: <code>${escapeHtml(kind)}</code></div>`);
        }
      }
    },
  hero(el, props, colors) {
      const t = props?.title ?? "Hero";
      const s = props?.subtitle ?? "";
      const body = props?.body ?? "";
      const ctaObj = props?.cta && typeof props.cta === 'object' ? props.cta : null;
      const label = props?.label ?? ctaObj?.label ?? ctaObj?.text ?? "";
      const href = props?.href ?? ctaObj?.href ?? ctaObj?.link ?? "#";
      const img = props?.image || props?.hero_image || null;
      el.innerHTML = `
        <section class="rounded-2xl p-6" data-role="hero">
          <h2 class="text-4xl font-extrabold tracking-wide">${escapeHtml(t)}</h2>
          ${s ? `<p class="mt-2 ${colors.primary.muted}">${escapeHtml(s)}</p>` : ""}
          ${body ? `<p class="mt-3 text-sm ${colors.primary.muted}">${formatText(body)}</p>` : ""}
          ${img ? `<img src="${escapeAttr(typeof img === 'string' ? img : (img?.url || img?.src || ''))}" alt="" class="mt-4 rounded-lg border border-slate-200 max-w-full h-auto" data-role="card">` : ""}
          ${label ? `<div class="mt-4"><a href="${escapeAttr(href)}" class="inline-block px-4 py-2 rounded text-white" data-role="cta-btn">${escapeHtml(label)}</a></div>` : ""}
        </section>
      `;
    },
    text(el, props, colors) {
      const t = props?.title ?? "Text";
      const sub = props?.subtitle ?? props?.tagline ?? "";
      const content = props?.content ?? null;
      const b = content ? sanitizeHtml(String(content)) : (props?.body ?? "");
      const label = props?.label ?? "";
      const href = props?.href ?? props?.link ?? "#";
      el.innerHTML = `
        <section class="p-4 border border-slate-200 rounded-lg bg-white" data-role="card">
          <h3 class="text-xl font-semibold mb-2">${escapeHtml(t)}</h3>
          ${sub ? `<p class="text-sm text-slate-600 mb-2">${escapeHtml(sub)}</p>` : ""}
          ${b ? `<p class="text-sm text-slate-600">${formatText(b)}</p>` : ""}
          ${label ? `<div class="mt-3"><a href="${escapeAttr(href)}" class="inline-block px-3 py-2 rounded text-white" data-role="cta-btn">${escapeHtml(label)}</a></div>` : ""}
        </section>
      `;
    },
    cta(el, props, colors) {
      const t = props?.title ?? "Call to action";
      const s = props?.subtitle ?? props?.description ?? "";
      const label = props?.label ?? props?.cta ?? "Start";
      const href = props?.href ?? props?.link ?? "#";
      el.innerHTML = `
        <section class="rounded-2xl text-white p-6 flex items-center justify-between" data-role="hero">
          <div>
            <p class="text-2xl font-bold">${escapeHtml(t)}</p>
            ${s ? `<p class="text-sm mt-1 ${colors.primary.muted}">${escapeHtml(s)}</p>` : ""}
          </div>
          <a href="${escapeAttr(href)}" class="px-4 py-2 rounded text-white" data-role="cta-btn">${escapeHtml(label)}</a>
        </section>
      `;
    },
    feature_grid(el, props, colors) {
      const title = props?.title ?? "Features";
      const subtitle = props?.subtitle ?? props?.description ?? "";
      const features = Array.isArray(props?.features) ? props.features : [];
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          <div class="mb-4">
            <h3 class="text-xl font-semibold">${escapeHtml(title)}</h3>
            ${subtitle ? `<p class="text-slate-600 text-sm mt-1">${escapeHtml(subtitle)}</p>` : ""}
          </div>
          <div class="grid gap-4 md:grid-cols-3">
            ${features
              .map((f) => `
                <div class="rounded-xl p-4 shadow-sm border border-slate-200" data-role="card">
                  ${f?.icon || f?.emoji ? `<div class="text-2xl mb-1">${escapeHtml(String(f.icon || f.emoji))}</div>` : ""}
                  <p class="font-medium">${escapeHtml(f?.title ?? "")}</p>
                  ${f?.description || f?.body ? `<p class="text-sm text-slate-600 mt-1">${escapeHtml(f.description || f.body)}</p>` : ""}
                </div>
              `)
              .join("")}
          </div>
        </section>
      `;
    },
    testimonial(el, props, colors) {
      const quote = props?.quote ?? "";
      const author = props?.author ?? "";
      const role = props?.role ?? props?.company ?? "";
      const avatar = props?.avatar || null;
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          <blockquote class="border-l-4 pl-4 italic text-slate-700">${escapeHtml(quote)}</blockquote>
          ${(author || role || avatar) ? `<div class="mt-3 flex items-center gap-3">${avatar ? `<img src="${escapeAttr(typeof avatar === 'string' ? avatar : (avatar?.url || avatar?.src || ''))}" alt="" class="h-8 w-8 rounded-full border border-slate-200">` : ""}<p class="text-sm text-slate-600">— ${escapeHtml(author)}${role ? `, ${escapeHtml(role)}` : ""}</p></div>` : ""}
        </section>
      `;
    },
    stats(el, props, colors) {
      const stats = Array.isArray(props?.stats) ? props.stats : [];
      if (!stats.length) { el.innerHTML = ''; return; }
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            ${stats.map(s => {
              const val = s?.value ?? s?.number ?? '';
              const lab = s?.label ?? s?.title ?? '';
              if (!val && !lab) return '';
              return `
                <div class="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center" data-role="card">
                  ${val ? `<div class="text-2xl font-extrabold">${escapeHtml(String(val))}</div>` : ''}
                  ${lab ? `<div class="text-xs text-slate-600 mt-1">${escapeHtml(String(lab))}</div>` : ''}
                </div>`;
            }).join('')}
          </div>
        </section>
      `;
    },
    pricing(el, props, colors) {
      const title = props?.title ?? 'Pricing';
      const items = Array.isArray(props?.items) ? props.items : [];
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          <h3 class="text-xl font-semibold">${escapeHtml(title)}</h3>
          <div class="mt-4 grid gap-4 md:grid-cols-2">
            ${items.map(it => {
              const name = it?.title || it?.name || '';
              const body = it?.body || it?.price || '';
              if (!name && !body) return '';
              return `
                <div class="p-4 rounded-xl border border-slate-200 bg-white" data-role="card">
                  ${name ? `<p class="font-medium">${escapeHtml(name)}</p>` : ''}
                  ${body ? `<p class="text-sm text-slate-600 mt-1">${escapeHtml(String(body))}</p>` : ''}
                </div>`;
            }).join('')}
          </div>
        </section>
      `;
    },
    gallery(el, props, colors) {
      const images = Array.isArray(props?.images) ? props.images : [];
      if (!images.length) { el.innerHTML = ''; return; }
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          <div class="grid gap-3 grid-cols-2 md:grid-cols-3">
            ${images.map(im => {
              const src = typeof im === 'string' ? im : (im?.url || im?.src || '');
              return src ? `<img src="${escapeAttr(src)}" alt="" class="rounded-lg border border-slate-200 w-full h-auto" data-role="card">` : '';
            }).join('')}
          </div>
        </section>
      `;
    },
    card_list(el, props, colors) {
      const title = props?.title ?? '';
      const items = Array.isArray(props?.items) ? props.items : [];
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white" data-role="card">
          ${title ? `<h3 class="text-xl font-semibold mb-2">${escapeHtml(title)}</h3>` : ''}
          <div class="space-y-3">
            ${items.map(it => {
              const name = it?.title || it?.name || '';
              const body = it?.body || it?.description || '';
              if (!name && !body) return '';
              return `
                <div class="p-3 border border-slate-200 rounded-lg bg-white" data-role="card">
                  ${name ? `<p class="font-medium">${escapeHtml(name)}</p>` : ''}
                  ${body ? `<p class="text-sm text-slate-600 mt-1">${formatText(body)}</p>` : ''}
                </div>`;
            }).join('')}
          </div>
        </section>
      `;
    },
  };

  const RENDERER_ALIASES = {
    features: "feature_grid",
    feature: "feature_grid",
    featuregrid: "feature_grid",
    paragraph: "text",
    copy: "text",
    body: "text",
    heading: "text",
    header: "hero",
    hero_block: "hero",
    call_to_action: "cta",
    calltoaction: "cta",
    button: "cta",
    quote: "testimonial",
    blockquote: "testimonial",
    review: "testimonial",
  };

  function getRenderer(type) {
    const t = String(type || "");
    const mapped = RENDERER_ALIASES[t] || t;
    return RENDERERS[mapped];
  }

  function enterSite(page) {
    const colors = resolveColors(page?.palette || {});
    const comps = Array.isArray(page?.components) ? page.components : [];
    const flow = (page?.layout && page.layout.flow) || 'stack';
    const wrapper = document.createElement('div');
    wrapper.className = 'container mx-auto max-w-4xl px-4 py-10';

    try {
      if (flow === 'grid') {
        const grid = document.createElement('div');
        grid.className = 'grid gap-5 md:grid-cols-2';
        for (const c of comps) {
          const type = normalizeType(c?.type);
          const props = c?.props || {};
          const fn = getRenderer(type) || renderGeneric;
          const el = document.createElement('div');
          el.className = '';
          fn(el, props, colors, type);
          grid.appendChild(el);
        }
        wrapper.appendChild(grid);
      } else {
        for (const c of comps) {
          const type = normalizeType(c?.type);
          const props = c?.props || {};
          const fn = getRenderer(type) || renderGeneric;
          const el = document.createElement('div');
          el.className = 'mb-5';
          fn(el, props, colors, type);
          wrapper.appendChild(el);
        }
      }
      const links = Array.isArray(page?.links) ? page.links : [];
      if (links.length) {
        const nav = document.createElement('nav');
        nav.className = 'mt-6 flex flex-wrap gap-4 text-sm';
        nav.innerHTML = links.map((href)=>`<a href="${escapeAttr(href)}" class="${colors.accent.text} hover:underline">${escapeHtml(href)}</a>`).join('');
        wrapper.appendChild(nav);
      }
    } catch (e) {
      console.error('Render failed:', e);
      const banner = document.createElement('div');
      banner.className = 'p-3 rounded bg-rose-50 border border-rose-200 text-rose-800';
      banner.textContent = 'Render failed. Please try again.';
      wrapper.innerHTML = '';
      wrapper.appendChild(banner);
    }

    mainEl.innerHTML = '';
    mainEl.appendChild(wrapper);
    applyPalette(page?.palette || {});
  }

  function setStatus() { /* removed status UI */ }

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
      throw new Error(`Generate failed (${resp.status}): ${text || resp.statusText}`);
    }
    return resp.json();
  }

  // Ensure at least one interactive widget exists in the page object.
  function ensureWidget(page) {
    try {
      const hasWidget = (Array.isArray(page?.components) ? page.components : []).some(c => String(c?.type||'').toLowerCase()==='widget');
      if (hasWidget) return page;
      const kinds = ['click_counter','dont_press','compliment_generator','color_party','emoji_rain','pixel_painter','yes_or_no','coin_flip','guess_number','tic_tac_toe'];
      const kind = kinds[Math.floor(Math.random()*kinds.length)];
      const widget = {
        id: `widget-${Math.floor(Math.random()*1e6)}`,
        type: 'widget',
        props: { kind }
      };
      const components = Array.isArray(page?.components) ? [...page.components, widget] : [widget];
      return { ...page, components };
    } catch { return page; }
  }

  function setGenerating(is) {
    const btns = [landingBtn, document.getElementById('floatingGenerate')].filter(Boolean);
    btns.forEach(b => { if (!b) return; if (is) { b.setAttribute('aria-busy','true'); b.disabled=true; } else { b.removeAttribute('aria-busy'); b.disabled=false; } });
  }

  async function generateNew(e) {
    if (e) e.preventDefault();
    const briefs = [
      'Emoji Rain Party', 'Tiny Painter Studio', 'Yes or No Oracle', 'Color Chaos Button', 'Coin-Flip Arena',
      'Guess-the-Number Mini', 'Pixel Paintboard', 'Speed Click Challenge', "Don't Press It", 'Mini Tic-Tac-Toe'
    ];
    const brief = briefs[Math.floor(Math.random()*briefs.length)];
    const seed = Math.floor(Math.random() * 1e9);
    const jsonOut = document.getElementById('jsonOut');
    if (jsonOut) jsonOut.textContent = '';
    setGenerating(true);
    showSpinner('Conjuring a new site…');
    const panel = document.getElementById('jsonPanel');
    const btn = document.getElementById('toggleJsonBtn');
    if (panel && !panel.classList.contains('hidden')) { panel.classList.add('hidden'); if (btn) btn.textContent = 'Show JSON'; }
    try {
      let page = await callGenerate(brief, seed);
      page = ensureWidget(page);
      enterSite(page);
      if (jsonOut) jsonOut.textContent = JSON.stringify(page, null, 2);
      ensureFloatingGenerate();
    } catch (err) {
      console.error('Generate error:', err);
    } finally {
      hideSpinner();
      setGenerating(false);
    }
  }

  function ensureFloatingGenerate() {
    // Remove landing button if we show floating button
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
    // The landing hero is server-rendered. Just ensure the button is wired.
    const lb = document.getElementById('landingGenerate');
    if (lb) lb.addEventListener('click', generateNew);
  }

  ensureFloatingGenerate();
  renderLanding();

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replaceAll('"', "&quot;");
  }
  function formatText(s) {
    return escapeHtml(String(s)).replaceAll("\n", "<br>");
  }

  function sanitizeHtml(html) {
    return String(html).replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "");
  }

  function normalizeType(t) {
    return String(t || "").toLowerCase().replaceAll("-", "_");
  }

  // Generic fallback renderer to show any component content.
  function renderGeneric(el, props, colors, type = "unknown") {
    const title = props?.title || type || "Section";
    const subtitle = props?.subtitle || props?.tagline || "";
    const body = props?.body || props?.content || props?.description || "";
    const label = props?.label || "";
    const href = props?.href || "#";
    const features = Array.isArray(props?.features) ? props.features : [];
    const items = Array.isArray(props?.items) ? props.items
                 : Array.isArray(props?.children) ? props.children
                 : Array.isArray(props?.blocks) ? props.blocks
                 : Array.isArray(props?.cards) ? props.cards
                 : [];
    const imgSrc = typeof props?.image === "string" ? props.image
                 : (props?.image && typeof props.image === "object" && (props.image.url || props.image.src))
                   ? (props.image.url || props.image.src)
                   : (typeof props?.src === "string" ? props.src : null);
    const imagesArr = Array.isArray(props?.images) ? props.images : [];
    const bullets = Array.isArray(props?.bullets) ? props.bullets
                   : Array.isArray(props?.points) ? props.points
                   : [];
    const faqs = Array.isArray(props?.faqs) ? props.faqs : [];
    const stats = Array.isArray(props?.stats) ? props.stats : [];
    const nestedCta = (props?.cta && typeof props.cta === "object") ? props.cta : null;

    const featureGrid = features.length
      ? `
        <div class="grid gap-4 md:grid-cols-3 mt-4">
          ${features.map(f => `
            <div class="rounded-xl p-4 shadow-sm border border-slate-200">
              ${f?.title ? `<p class="font-medium">${escapeHtml(f.title)}</p>` : ""}
              ${f?.body ? `<p class="text-sm text-slate-600 mt-1">${formatText(f.body)}</p>` : ""}
            </div>
          `).join("")}
        </div>
      ` : "";

    const itemList = items.length
      ? `
        <div class="mt-4 space-y-3">
          ${items.map(it => {
            const itTitle = it?.title || it?.name || "";
            const itBody = it?.body || it?.description || "";
            return `
              <div class="p-3 border border-slate-200 rounded-lg bg-white">
                ${itTitle ? `<p class="font-medium">${escapeHtml(itTitle)}</p>` : ""}
                ${itBody ? `<p class="text-sm text-slate-600 mt-1">${formatText(itBody)}</p>` : ""}
              </div>
            `;
          }).join("")}
        </div>
      ` : "";

    const imageBlock = imgSrc
      ? `<div class="mt-4"><img src="${escapeAttr(imgSrc)}" alt="" class="rounded-lg border border-slate-200 max-w-full h-auto"></div>`
      : "";

    const imageGallery = imagesArr.length
      ? `
        <div class="mt-4 grid gap-3 grid-cols-2 md:grid-cols-3">
          ${imagesArr.map(im => {
            const src = typeof im === "string" ? im : (im?.url || im?.src || "");
            return src ? `<img src="${escapeAttr(src)}" alt="" class="rounded-lg border border-slate-200 w-full h-auto">` : "";
          }).join("")}
        </div>
      ` : "";

    const bulletList = bullets.length
      ? `
        <ul class="mt-3 list-disc list-inside text-slate-700 space-y-1">
          ${bullets.map(b => `<li>${formatText(String(b))}</li>`).join("")}
        </ul>
      ` : "";

    const faqList = faqs.length
      ? `
        <div class="mt-4 space-y-3">
          ${faqs.map(f => {
            const q = f?.q || f?.question || "";
            const a = f?.a || f?.answer || "";
            return `
              <details class="p-3 border border-slate-200 rounded-lg bg-white">
                <summary class="font-medium cursor-pointer">${escapeHtml(q)}</summary>
                ${a ? `<div class="text-sm text-slate-600 mt-1">${formatText(a)}</div>` : ""}
              </details>`;
          }).join("")}
        </div>
      ` : "";

    const statsGrid = stats.length
      ? `
        <div class="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          ${stats.map(s => {
            const val = s?.value ?? s?.number ?? "";
            const lab = s?.label ?? s?.title ?? "";
            return `
              <div class="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                <div class="text-2xl font-extrabold">${escapeHtml(String(val))}</div>
                ${lab ? `<div class="text-xs text-slate-600 mt-1">${escapeHtml(String(lab))}</div>` : ""}
              </div>`;
          }).join("")}
        </div>
      ` : "";

    const nestedCtaBtn = nestedCta && (nestedCta.label || nestedCta.text)
      ? `<div class="mt-4"><a href="${escapeAttr(nestedCta.href || "#")}" class="inline-block px-3 py-2 rounded text-white" data-role="cta-btn">${escapeHtml(nestedCta.label || nestedCta.text)}</a></div>`
      : "";

    const knownKeys = new Set(["title","subtitle","tagline","body","content","description","label","href","features","items","children","blocks","cards","image","images","src","bullets","points","faqs","stats","cta"]);
    const rest = {};
    Object.keys(props || {}).forEach(k => { if (!knownKeys.has(k)) rest[k] = props[k]; });
    const restDump = Object.keys(rest).length
      ? `<details class="mt-4 text-xs text-slate-500"><summary>Raw props</summary><pre class="mt-2 whitespace-pre-wrap">${escapeHtml(JSON.stringify(rest, null, 2))}</pre></details>`
      : "";

    el.innerHTML = `
      <section class="p-6 rounded-2xl border border-slate-200 bg-white">
        <h3 class="text-xl font-semibold">${escapeHtml(title)}</h3>
        ${subtitle ? `<p class="text-slate-600 text-sm mt-1">${escapeHtml(subtitle)}</p>` : ""}
        ${body ? `<p class="text-slate-700 text-sm mt-3">${formatText(body)}</p>` : ""}
        ${imageBlock}
        ${imageGallery}
        ${featureGrid}
        ${itemList}
        ${bulletList}
        ${faqList}
        ${statsGrid}
        ${label ? `<div class="mt-4"><a href="${escapeAttr(href)}" class="inline-block px-3 py-2 rounded text-white ${colors.accent.btn}">${escapeHtml(label)}</a></div>` : ""}
        ${nestedCtaBtn}
        ${restDump}
      </section>
    `;
  }

  function paletteHex(colors) {
    const prim = colors.primary;
    const acc = colors.accent;
    const P = {
      slate: { bg: "#0f172a", muted: "#cbd5e1" },
      gray: { bg: "#111827", muted: "#d1d5db" },
      stone: { bg: "#1c1917", muted: "#d6d3d1" },
      zinc: { bg: "#0303ffff", muted: "#d4d4d8" },
      neutral: { bg: "#171717", muted: "#d4d4d4" },
    };
    const A = {
      indigo: "#4f46e5",
      violet: "#7c3aed",
      emerald: "#10b981",
      sky: "#0ea5e9",
      rose: "#e11d48",
    };
    const pb = (P[prim] || P.slate).bg;
    const pm = (P[prim] || P.slate).muted;
    const ac = A[acc] || A.indigo;
    return { primaryBg: pb, primaryMuted: pm, accent: ac };
  }

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
