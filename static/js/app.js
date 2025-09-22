const API_KEY = 'demo_123'; // Dev only. Remove for public deployments.

const $ = (sel, el = document) => el.querySelector(sel);
const root = $('#app');
const briefInput = $('#brief');
const seedInput = $('#seed');
const btn = $('#go');
const remainingEl = $('#remaining');

const PALETTE = {
  slate:  '#334155',
  gray:   '#374151',
  indigo: '#4f46e5',
  blue:   '#2563eb',
  teal:   '#0d9488',
  rose:   '#e11d48',
  emerald:'#10b981',
};

function applyPalette(palette) {
  if (!palette) return;
  document.documentElement.style.setProperty('--primary', PALETTE[palette.primary] || '#334155');
  document.documentElement.style.setProperty('--accent',  PALETTE[palette.accent]  || '#4f46e5');
}


function renderHero(component) {
  const { title = 'Untitled', subtitle = '' } = component.props || {};
  const sec = document.createElement('section');
  sec.className = 'hero';

  const h1 = document.createElement('h1');
  h1.textContent = title;

  const p = document.createElement('p');
  p.className = 'sub';
  p.textContent = subtitle;

  sec.append(h1, p);
  return sec;
}

function renderUnknown(component) {
  const pre = document.createElement('pre');
  pre.textContent = `Unknown component: ${component.type}`;
  return pre;
}

function renderPage(page) {
  root.innerHTML = '';
  applyPalette(page.palette);

  const { components = [] } = page;
  for (const comp of components) {
    let el;
    switch (comp.type) {
      case 'hero': el = renderHero(comp); break;
      default:     el = renderUnknown(comp);
    }
    root.appendChild(el);
  }
}


async function generate(brief, seed) {
  const resp = await fetch('/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': API_KEY, // required while API_KEYS is set in .env
    },
    body: JSON.stringify({
      brief: brief || 'Landing page',
      seed: seed !== '' ? Number(seed) : undefined,
    }),
  });

  const rem = resp.headers.get('X-RateLimit-Remaining');
  if (rem !== null) {
    remainingEl.textContent = `Requests left: ${rem}`;
  } else {
    remainingEl.textContent = '';
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`Generate failed: ${resp.status} ${text}`);
  }

  return resp.json();
}


btn.addEventListener('click', async () => {
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = 'Generating…';
  try {
    const page = await generate(briefInput.value, seedInput.value);
    renderPage(page);
  } catch (err) {
    root.innerHTML = `<pre>${(err?.message || String(err))}</pre>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

// Auto-fill some defaults and optionally trigger a first render
window.addEventListener('DOMContentLoaded', async () => {
  if (!briefInput.value) briefInput.value = 'Coffee shop';
  if (!seedInput.value) seedInput.value = '1';
  // Uncomment to auto-generate on load:
  // btn.click();
});
