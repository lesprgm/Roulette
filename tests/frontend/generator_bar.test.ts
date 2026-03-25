// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

let ensureFloatingGenerate: typeof import('../../static/ts-src/app').__ndwTestEnsureFloatingGenerate;
let getGenerationQuality: typeof import('../../static/ts-src/app').__ndwTestGetGenerationQuality;
let setGenerationQuality: typeof import('../../static/ts-src/app').__ndwTestSetGenerationQuality;
let setBodyMode: typeof import('../../static/ts-src/app').__ndwTestSetBodyMode;

describe('Generator bar', () => {
  beforeEach(async () => {
    (window as any).__ndwDisableAutoInit = true;
    const mod = await import('../../static/ts-src/app');
    ensureFloatingGenerate = mod.__ndwTestEnsureFloatingGenerate;
    getGenerationQuality = mod.__ndwTestGetGenerationQuality;
    setGenerationQuality = mod.__ndwTestSetGenerationQuality;
    setBodyMode = mod.__ndwTestSetBodyMode;
    window.localStorage.clear();
    document.body.className = '';
    document.body.innerHTML = `
      <div id="appMain"></div>
      <div id="landingFallback" hidden></div>
      <div id="ndwTestPreviewDock" hidden></div>
    `;
    setGenerationQuality('fast');
  });

  afterEach(() => {
    document.body.innerHTML = '';
    document.body.className = '';
    window.localStorage.clear();
    delete (window as any).__ndwDisableAutoInit;
  });

  it('does not render the generator bar while landing mode is active', () => {
    setBodyMode('landing');
    ensureFloatingGenerate();

    expect(document.getElementById('floatingGenerateWrap')).toBeNull();
  });

  it('renders the generator bar in generated mode', () => {
    setBodyMode('generated');
    ensureFloatingGenerate();

    const wrap = document.getElementById('floatingGenerateWrap');
    const counterCard = document.getElementById('sitesCounterFloating');
    const modeWrap = document.getElementById('generationModeWrap');
    expect(wrap).not.toBeNull();
    expect(counterCard).not.toBeNull();
    expect(counterCard?.contains(wrap as Node)).toBe(false);
    expect(counterCard?.contains(modeWrap as Node)).toBe(true);
    expect(modeWrap?.textContent).toContain('Mode: Fast');
    expect(document.getElementById('floatingGenerate')).not.toBeNull();
  });

  it('persists and syncs quality state across generator bar mounts', () => {
    setBodyMode('generated');
    ensureFloatingGenerate();
    setGenerationQuality('premium');

    expect(getGenerationQuality()).toBe('premium');
    expect(window.localStorage.getItem('ndw_generation_quality')).toBe('premium');
    expect(document.querySelector('[data-ndw-mode-label="1"]')?.textContent).toContain('Premium');
    expect(document.querySelector('[data-quality-mode="premium"]')?.getAttribute('aria-checked')).toBe('true');

    document.getElementById('floatingGenerateWrap')?.remove();
    document.getElementById('generationModeWrap')?.remove();
    ensureFloatingGenerate();

    expect(document.querySelector('[data-ndw-mode-label="1"]')?.textContent).toContain('Premium');
    expect(document.querySelector('[data-quality-mode="premium"]')?.getAttribute('aria-checked')).toBe('true');
  });
});
