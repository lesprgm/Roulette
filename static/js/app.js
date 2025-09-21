async function callGenerate() {
  const brief = document.getElementById('brief').value || '';
  const seedVal = document.getElementById('seed').value;
  const apikey = document.getElementById('apikey').value || '';
  const seed = seedVal ? Number(seedVal) : null;

  const res = await fetch('/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(apikey ? { 'x-api-key': apikey } : {})
    },
    body: JSON.stringify({ brief, seed })
  });

  let data;
  try {
    data = await res.json();
  } catch {
    data = { error: 'Non-JSON response', status: res.status };
  }
  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  if (res.ok) renderPage(data);
}

function renderPage(page) {
  const root = document.getElementById('render');
  root.innerHTML = '';

  const palette = page.palette || {};
  const accent = palette.accent || 'indigo';

  (page.components || []).forEach(c => {
    switch (c.type) {
      case 'hero': {
        const div = document.createElement('div');
        div.className = "mt-4 p-8 bg-white rounded-2xl shadow";
        div.innerHTML = `
          <h2 class="text-3xl font-bold text-${accent}-600">${c.props?.title || 'Untitled'}</h2>
          <p class="mt-2 text-slate-600">${c.props?.subtitle || ''}</p>
        `;
        root.appendChild(div);
        break;
      }
      case 'card': {
        const div = document.createElement('div');
        div.className = "mt-4 p-6 bg-white rounded-xl shadow";
        div.innerHTML = `
          <div class="font-semibold text-slate-800">${c.props?.title || 'Card'}</div>
          <p class="mt-1 text-slate-600">${c.props?.body || ''}</p>
        `;
        root.appendChild(div);
        break;
      }
      case 'cta': {
        const div = document.createElement('div');
        div.className = "mt-4 p-6 bg-white rounded-xl shadow flex items-center gap-3";
        div.innerHTML = `
          <div class="flex-1">
            <div class="font-semibold text-slate-800">${c.props?.title || 'Call to action'}</div>
            <p class="mt-1 text-slate-600">${c.props?.subtitle || ''}</p>
          </div>
          <a href="${c.props?.href || '#'}" class="px-4 py-2 bg-${accent}-600 text-white rounded hover:bg-${accent}-700">
            ${c.props?.label || 'Learn more'}
          </a>
        `;
        root.appendChild(div);
        break;
      }
      case 'grid': {
        const cols = Math.min(Math.max(Number(c.props?.columns || 3), 1), 4);
        const div = document.createElement('div');
        div.className = "mt-4 grid gap-4 " + ({
          1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3", 4: "grid-cols-4"
        }[cols]);
        (c.props?.items || []).forEach(item => {
          const card = document.createElement('div');
          card.className = "p-4 bg-white rounded-xl shadow";
          card.innerHTML = `
            <div class="font-semibold text-slate-800">${item.title || 'Item'}</div>
            <p class="mt-1 text-slate-600">${item.body || ''}</p>
          `;
          div.appendChild(card);
        });
        root.appendChild(div);
        break;
      }
      case 'text': {
        const p = document.createElement('p');
        p.className = "mt-3 text-slate-700";
        p.textContent = c.props?.content || '';
        root.appendChild(p);
        break;
      }
      case 'image': {
        const img = document.createElement('img');
        img.className = "mt-4 rounded-xl shadow";
        img.src = c.props?.src || '';
        img.alt = c.props?.alt || '';
        root.appendChild(img);
        break;
      }
      default: {
        const pre = document.createElement('pre');
        pre.className = "mt-4 p-4 bg-white rounded shadow overflow-x-auto text-xs";
        pre.textContent = JSON.stringify(c, null, 2);
        root.appendChild(pre);
      }
    }
  });
}

document.getElementById('go').addEventListener('click', callGenerate);
