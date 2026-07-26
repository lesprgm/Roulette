import { buildGeneratedFrame, extractDocumentTitle } from './frame_renderer.js';

let activeFrame: HTMLIFrameElement | null = null;

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function resetHostRoot(target: HTMLElement): void {
  target.removeAttribute('style');
  target.className = 'w-full min-h-screen';
  target.removeAttribute('data-ndw-fullpage-root');
  target.innerHTML = '';
}

export function destroyGeneratedSiteFrame(): void {
  activeFrame?.remove();
  activeFrame = null;
}

export function renderFullPageHost(target: HTMLElement, html: string): void {
  document.querySelectorAll('style[data-gen-style="1"], style[data-ndw-sandbox="1"]').forEach(style => style.remove());
  document.body.style.cssText = '';
  const hostClasses = new Set(['ndw-base', 'generated-mode', 'ndw-eval-hide-chrome']);
  document.body.className = Array.from(document.body.classList).filter(name => hostClasses.has(name)).join(' ');
  document.body.classList.add('generated-mode');
  destroyGeneratedSiteFrame();
  resetHostRoot(target);
  activeFrame = buildGeneratedFrame(html);
  target.appendChild(activeFrame);
  const title = extractDocumentTitle(html);
  if (title) document.title = title;
}

export function showHostError(target: HTMLElement, message: string): void {
  const wrap = document.createElement('div');
  wrap.className = 'max-w-xl mx-auto mt-8 px-4';
  wrap.innerHTML = `<div class="p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">${escapeHtml(message || 'Error')}</div>`;
  target.innerHTML = '';
  target.appendChild(wrap);
}
