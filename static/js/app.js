async function callGenerate() {
  const brief = document.getElementById('brief').value || '';
  const seedVal = document.getElementById('seed').value;
  const seed = seedVal ? Number(seedVal) : null;

  const res = await fetch('/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ brief, seed })
  });
  const data = await res.json();

  document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  renderPage(data);
}

function renderPage(page) {
  const root = document.getElementById('render');
  root.innerHTML = '';

  (page.components || []).forEach(c => {
    if (c.type === 'hero') {
      const div = document.createElement('div');
      div.className = "mt-4 p-8 bg-white rounded-2xl shadow";
      div.innerHTML = `
        <h2 class="text-3xl font-bold text-indigo-600">${c.props?.title || 'Untitled'}</h2>
        <p class="mt-2 text-slate-600">${c.props?.subtitle || ''}</p>
      `;
      root.appendChild(div);
    }
  });
}

document.getElementById('go').addEventListener('click', callGenerate);
