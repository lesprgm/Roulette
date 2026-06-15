export function extractDocumentTitle(html) {
    const match = String(html || '').match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    if (!match)
        return '';
    const doc = document.implementation.createHTMLDocument('');
    doc.body.innerHTML = match[1];
    return (doc.body.textContent || '').trim();
}
export function buildGeneratedFrame(html) {
    const iframe = document.createElement('iframe');
    iframe.id = 'ndw-site-frame';
    iframe.className = 'w-full min-h-screen border-none ndw-site-frame';
    iframe.title = 'Generated website';
    iframe.setAttribute('sandbox', 'allow-scripts allow-popups');
    iframe.setAttribute('loading', 'eager');
    iframe.style.display = 'block';
    iframe.style.width = '100%';
    iframe.style.minHeight = '100vh';
    iframe.style.border = '0';
    iframe.srcdoc = injectIframeBridge(html);
    return iframe;
}
function injectIframeBridge(html) {
    const bridge = `
<script>
(() => {
  window.NDW = window.NDW || {};
  window.NDW.registerCleanup = window.NDW.registerCleanup || function(){};
  document.addEventListener('click', (event) => {
    const target = event.target && event.target.closest ? event.target.closest('button,a,[role="button"],[data-ndw-trigger]') : null;
    if (!target) return;
    const trigger = String(target.getAttribute('data-ndw-trigger') || '').toLowerCase();
    if (trigger === 'generate' || trigger === 'new-site') {
      event.preventDefault();
      window.parent.postMessage({ type: 'NDW_GENERATE' }, '*');
    }
  }, true);
})();
</script>`;
    const base = `<base href="${window.location.origin}/">`;
    let out = String(html || '');
    if (/<head[^>]*>/i.test(out)) {
        if (!/<base\s/i.test(out)) {
            out = out.replace(/<head([^>]*)>/i, `<head$1>${base}`);
        }
        return out.replace(/<\/body\s*>/i, `${bridge}</body>`);
    }
    return `<!doctype html><html><head>${base}</head><body>${out}${bridge}</body></html>`;
}
