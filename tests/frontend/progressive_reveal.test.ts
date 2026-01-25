// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

let hideLandingElements: typeof import('../../static/ts-src/app').hideLandingElements;
let prepareReveal: typeof import('../../static/ts-src/app').prepareReveal;
let playReveal: typeof import('../../static/ts-src/app').playReveal;
let updateJsonOut: typeof import('../../static/ts-src/app').updateJsonOut;

describe('Progressive Reveal', () => {
  let mainEl: HTMLElement;

  beforeEach(async () => {
    (window as any).__ndwDisableAutoInit = true;
    const mod = await import('../../static/ts-src/app');
    hideLandingElements = mod.hideLandingElements;
    prepareReveal = mod.prepareReveal;
    playReveal = mod.playReveal;
    updateJsonOut = mod.updateJsonOut;
    document.body.innerHTML = '<div id="appMain"></div>';
    mainEl = document.getElementById('appMain')!;
  });

  afterEach(() => {
    document.body.innerHTML = '';
    delete (window as any).__ndwDisableAutoInit;
  });

  it('hideLandingElements removes target elements', () => {
    document.body.innerHTML = `
      <div class="blob-cont"></div>
      <div class="noise-overlay"></div>
      <div id="cursor-glow"></div>
      <div id="tunnel-container"></div>
      <div id="unrelated"></div>
    `;
    document.body.style.minHeight = '10000vh';
    document.body.style.background = 'linear-gradient(90deg,#000,#fff)';
    hideLandingElements();
    expect(document.querySelector('.blob-cont')).toBeNull();
    expect(document.querySelector('.noise-overlay')).toBeNull();
    expect(document.getElementById('cursor-glow')).toBeNull();
    expect(document.getElementById('tunnel-container')?.style.display).toBe('none');
    expect(document.body.classList.contains('generated-mode')).toBe(true);
    expect(document.body.style.minHeight).toBe('');
    expect(document.body.style.background).toBe('');
    expect(document.getElementById('unrelated')).not.toBeNull();
  });

  it('prepareReveal is a no-op and restores opacity', async () => {
    mainEl.innerHTML = '<h1>Header</h1><main>Content</main><button>Btn</button>';
    mainEl.style.opacity = '0';

    await prepareReveal();

    expect(mainEl.style.opacity).toBe('1');
  });

  it('playReveal is a no-op and restores opacity', async () => {
    mainEl.innerHTML = '<h1>Header</h1><main>Content</main>';
    mainEl.style.opacity = '0';

    await playReveal();

    expect(mainEl.style.opacity).toBe('1');
  });

  it('updateJsonOut writes JSON to panel', () => {
    document.body.innerHTML = '<div id="jsonOut"></div>';
    updateJsonOut({ ok: true, value: 42 });
    const out = document.getElementById('jsonOut')!;
    expect(out.textContent).toContain('"ok": true');
    expect(out.textContent).toContain('"value": 42');
  });
});
