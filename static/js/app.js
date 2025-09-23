(function () {
  const $ = (sel) => document.querySelector(sel);
  const bodyEl = document.body;

  const statusEl = $("#status");
  const preview = $("#preview");
  const jsonPanel = $("#jsonPanel");
  const jsonOut = $("#jsonOut");
  const toggleBtn = $("#toggleJsonBtn");
  const generateBtn = $("#generateBtn") || $("#generate");

  function updateToggleText() {
    const open = !jsonPanel.classList.contains("hidden");
    toggleBtn.setAttribute("aria-expanded", String(open));
    toggleBtn.textContent = open ? "Hide JSON" : "Show JSON";
  }
  toggleBtn.addEventListener("click", () => {
    jsonPanel.classList.toggle("hidden");
    updateToggleText();
  });
  if (!jsonPanel.classList.contains("hidden")) jsonPanel.classList.add("hidden");
  updateToggleText();

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
  };

  function applyPalette(palette) {
    const p = (palette?.primary && PALETTES[palette.primary]) ? palette.primary : 'slate';
    const pal = PALETTES[p];
    document.querySelectorAll('[data-role="hero"]').forEach((el) => {
      el.classList.add(pal.bg, pal.text);
    });
    document.querySelectorAll('[data-role="cta-btn"]').forEach((el) => {
      el.classList.add(...pal.accentBtn.split(' '), pal.accentText);
    });
    document.querySelectorAll('[data-role="card"]').forEach((el) => {
      el.classList.add(pal.card);
    });
  }

  const RENDERERS = {
    hero(el, props, colors) {
      const t = props?.title ?? "Hero";
      const s = props?.subtitle ?? "";
      const body = props?.body ?? "";
      const ctaObj = props?.cta && typeof props.cta === 'object' ? props.cta : null;
      const label = props?.label ?? ctaObj?.label ?? ctaObj?.text ?? "";
      const href = props?.href ?? ctaObj?.href ?? ctaObj?.link ?? "#";
      const img = props?.image || props?.hero_image || null;
      el.innerHTML = `
        <section class="rounded-2xl p-6 ${colors.primary.sectionBg} ${colors.primary.sectionText}" data-role="hero">
          <h2 class="text-4xl font-extrabold tracking-wide">${escapeHtml(t)}</h2>
          ${s ? `<p class="mt-2 ${colors.primary.muted}">${escapeHtml(s)}</p>` : ""}
          ${body ? `<p class="mt-3 text-sm ${colors.primary.muted}">${formatText(body)}</p>` : ""}
          ${img ? `<img src="${escapeAttr(typeof img === 'string' ? img : (img?.url || img?.src || ''))}" alt="" class="mt-4 rounded-lg border border-slate-200 max-w-full h-auto" data-role="card">` : ""}
          ${label ? `<div class="mt-4"><a href="${escapeAttr(href)}" class="inline-block px-4 py-2 rounded text-white ${colors.accent.btn}" data-role="cta-btn">${escapeHtml(label)}</a></div>` : ""}
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
          ${label ? `<div class="mt-3"><a href="${escapeAttr(href)}" class="inline-block px-3 py-2 rounded text-white ${colors.accent.btn}" data-role="cta-btn">${escapeHtml(label)}</a></div>` : ""}
        </section>
      `;
    },
    cta(el, props, colors) {
      const t = props?.title ?? "Call to action";
      const s = props?.subtitle ?? props?.description ?? "";
      const label = props?.label ?? props?.cta ?? "Start";
      const href = props?.href ?? props?.link ?? "#";
      el.innerHTML = `
        <section class="rounded-2xl text-white p-6 flex items-center justify-between ${colors.primary.sectionBg}" data-role="hero">
          <div>
            <p class="text-2xl font-bold">${escapeHtml(t)}</p>
            ${s ? `<p class="text-sm mt-1 ${colors.primary.muted}">${escapeHtml(s)}</p>` : ""}
          </div>
          <a href="${escapeAttr(href)}" class="px-4 py-2 rounded text-white ${colors.accent.btn}" data-role="cta-btn">${escapeHtml(label)}</a>
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

  function renderPage(page) {
    preview.innerHTML = "";
    const colors = resolveColors(page?.palette || {});
    const comps = Array.isArray(page?.components) ? page.components : [];
    const flow = (page?.layout && page.layout.flow) || "stack";

    try {
      if (flow === "grid") {
        const grid = document.createElement("div");
        grid.className = "grid gap-5 md:grid-cols-2";
        for (const c of comps) {
          const type = normalizeType(c?.type);
          const props = c?.props || {};
          const fn = getRenderer(type) || renderGeneric;
          const el = document.createElement("div");
          el.className = ""; // spacing handled by grid gap
          fn(el, props, colors, type);
          grid.appendChild(el);
        }
        preview.appendChild(grid);
      } else {
        for (const c of comps) {
          const type = normalizeType(c?.type);
          const props = c?.props || {};
          const fn = getRenderer(type) || renderGeneric;
          const el = document.createElement("div");
          el.className = "mb-5";
          fn(el, props, colors, type);
          preview.appendChild(el);
        }
      }
      applyPalette(page?.palette || {});
    } catch (e) {
      console.error('Render failed:', e);
      const banner = document.createElement('div');
      banner.className = 'p-3 rounded bg-rose-50 border border-rose-200 text-rose-800';
      banner.textContent = 'Render failed. Please try again.';
      preview.innerHTML = '';
      preview.appendChild(banner);
    }

    const links = Array.isArray(page?.links) ? page.links : [];
    if (links.length > 0) {
      const nav = document.createElement("nav");
      nav.className = "mt-6 flex flex-wrap gap-4 text-sm";
      nav.innerHTML = links
        .map((href) => `<a href="${escapeAttr(href)}" class="${colors.accent.text} hover:underline">${escapeHtml(href)}</a>`) 
        .join("");
      preview.appendChild(nav);
    }
  }

  function setStatus(msg, kind = "info") {
    const colors = {
      info: "text-slate-600",
      ok: "text-green-700",
      warn: "text-amber-700",
      err: "text-red-700",
    };
    statusEl.className = `mt-2 text-sm ${colors[kind] || colors.info}`;
    statusEl.textContent = msg;
  }

  async function callGenerateEmpty() {
    const resp = await fetch("/generate", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": API_KEY,
      },
      // Backend currently expects 'brief' (min_length=1). Send a single space
      // to trigger the auto-theme path without 422 validation errors.
      body: JSON.stringify({ brief: " " }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Generate failed (${resp.status}): ${text || resp.statusText}`);
    }
    return resp.json();
  }

  if (generateBtn) {
    generateBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      setStatus("Generating…", "info");
      preview.innerHTML = "";
      jsonOut.textContent = "";
      // Disable button while generating
      generateBtn.setAttribute("aria-busy", "true");
      generateBtn.disabled = true;
      showSpinner();
      if (!jsonPanel.classList.contains("hidden")) {
        jsonPanel.classList.add("hidden");
        updateToggleText();
      }
      try {
        const page = await callGenerateEmpty();
        renderPage(page);
        // Update JSON with the exact object used to render
        jsonOut.textContent = JSON.stringify(page, null, 2);
        const palette = page?.palette || {};
        const comps = Array.isArray(page?.components) ? page.components.length : 0;
        setStatus(`Done. seed=${page?.seed ?? "?"} • palette=${palette.primary || "?"}/${palette.accent || "?"} • components=${comps}`, "ok");
      } catch (err) {
        setStatus("Render failed: " + String(err.message || err), "err");
        preview.innerHTML = "";
      } finally {
        hideSpinner();
        generateBtn.removeAttribute("aria-busy");
        generateBtn.disabled = false;
      }
    });
  }

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
      ? `<div class="mt-4"><a href="${escapeAttr(nestedCta.href || "#")}" class="inline-block px-3 py-2 rounded text-white ${colors.accent.btn}">${escapeHtml(nestedCta.label || nestedCta.text)}</a></div>`
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
      el.className = "hidden fixed inset-0 grid place-items-center bg-black/30 z-50";
      el.innerHTML = `
        <div class="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent"></div>
      `;
      document.body.appendChild(el);
    }
    return el;
  }
  function showSpinner() { ensureSpinner().classList.remove("hidden"); }
  function hideSpinner() { ensureSpinner().classList.add("hidden"); }
})();
