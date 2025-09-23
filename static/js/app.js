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
  // Hide JSON by default on first load
  if (!jsonPanel.classList.contains("hidden")) jsonPanel.classList.add("hidden");
  updateToggleText();

  const API_KEY =
    (window.API_KEY && String(window.API_KEY)) ||
    (bodyEl.dataset.apiKey && String(bodyEl.dataset.apiKey)) ||
    "demo_123";

  const DEFAULT_COLORS = { primary: "slate", accent: "indigo" };
  function resolveColors(palette) {
    const primary = (palette?.primary || DEFAULT_COLORS.primary);
    const accent = (palette?.accent || DEFAULT_COLORS.accent);
    const safe = (name, allowed) => (allowed.includes(name) ? name : allowed[0]);
    const primaries = ["slate", "gray", "stone", "zinc", "neutral"];
    const accents = ["indigo", "violet", "emerald", "sky", "rose"];
    return {
      primary: safe(primary, primaries),
      accent: safe(accent, accents),
    };
  }

  const RENDERERS = {
    hero(el, props, colors) {
      const t = props?.title ?? "Hero";
      const s = props?.subtitle ?? "";
      const pal = paletteHex(colors);
      el.innerHTML = `
        <section class="rounded-2xl p-6 text-white" style="background:${pal.primaryBg};">
          <h2 class="text-4xl font-extrabold tracking-wide">${escapeHtml(t)}</h2>
          ${s ? `<p class="mt-2" style="color:${pal.primaryMuted}">${escapeHtml(s)}</p>` : ""}
        </section>
      `;
    },
    text(el, props, colors) {
      const t = props?.title ?? "Text";
      const b = props?.body ?? "";
      el.innerHTML = `
        <section class="p-4 border border-slate-200 rounded-lg bg-white">
          <h3 class="text-xl font-semibold mb-2">${escapeHtml(t)}</h3>
          ${b ? `<p class="text-sm text-slate-600">${escapeHtml(b)}</p>` : ""}
        </section>
      `;
    },
    cta(el, props, colors) {
      const t = props?.title ?? "Call to action";
      const s = props?.subtitle ?? "";
      const label = props?.label ?? "Start";
      const href = props?.href ?? "#";
      const pal = paletteHex(colors);
      el.innerHTML = `
        <section class="rounded-2xl text-white p-6 flex items-center justify-between" style="background:${pal.primaryBg};">
          <div>
            <p class="text-2xl font-bold">${escapeHtml(t)}</p>
            ${s ? `<p class="text-sm mt-1" style="color:${pal.primaryMuted}">${escapeHtml(s)}</p>` : ""}
          </div>
          <a href="${escapeAttr(href)}" class="px-4 py-2 rounded text-white" style="background:${pal.accent};">${escapeHtml(label)}</a>
        </section>
      `;
    },
    feature_grid(el, props, colors) {
      const title = props?.title ?? "Features";
      const subtitle = props?.subtitle ?? "";
      const features = Array.isArray(props?.features) ? props.features : [];
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white">
          <div class="mb-4">
            <h3 class="text-xl font-semibold">${escapeHtml(title)}</h3>
            ${subtitle ? `<p class="text-slate-600 text-sm mt-1">${escapeHtml(subtitle)}</p>` : ""}
          </div>
          <div class="grid gap-4 md:grid-cols-3">
            ${features
              .map((f) => `
                <div class="rounded-xl p-4 shadow-sm border border-slate-200">
                  <p class="font-medium">${escapeHtml(f?.title ?? "")}</p>
                  ${f?.body ? `<p class="text-sm text-slate-600 mt-1">${escapeHtml(f.body)}</p>` : ""}
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
      const role = props?.role ?? "";
      el.innerHTML = `
        <section class="p-6 rounded-2xl border border-slate-200 bg-white">
          <blockquote class="border-l-4 pl-4 italic text-slate-700">${escapeHtml(quote)}</blockquote>
          ${(author || role) ? `<p class="mt-2 text-sm text-slate-600">— ${escapeHtml(author)}${role ? `, ${escapeHtml(role)}` : ""}</p>` : ""}
        </section>
      `;
    },
  };

  function renderPage(page) {
    preview.innerHTML = "";
    const colors = resolveColors(page?.palette || {});
    for (const c of page?.components || []) {
      const type = c?.type;
      const props = c?.props || {};
      const renderer = RENDERERS[type];
      if (!renderer) continue; // silently skip unknown
      const el = document.createElement("div");
      el.className = "mb-5";
      renderer(el, props, colors);
      preview.appendChild(el);
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
      jsonOut.textContent = "";
      if (!jsonPanel.classList.contains("hidden")) {
        jsonPanel.classList.add("hidden");
        updateToggleText();
      }
      try {
        const page = await callGenerateEmpty();
        renderPage(page);
        jsonOut.textContent = JSON.stringify(page, null, 2);
        setStatus("Done.", "ok");
      } catch (err) {
        setStatus(String(err.message || err), "err");
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

  // Palette hex mapping to avoid relying on dynamic Tailwind classes.
  function paletteHex(colors) {
    const prim = colors.primary;
    const acc = colors.accent;
    const P = {
      slate: { bg: "#0f172a", muted: "#cbd5e1" },
      gray: { bg: "#111827", muted: "#d1d5db" },
      stone: { bg: "#1c1917", muted: "#d6d3d1" },
      zinc: { bg: "#18181b", muted: "#d4d4d8" },
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
})();
