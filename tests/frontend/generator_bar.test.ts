// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

let ensureFloatingGenerate: typeof import('../../static/ts-src/app').__ndwTestEnsureFloatingGenerate;
let setBodyMode: typeof import('../../static/ts-src/app').__ndwTestSetBodyMode;

describe('Generator bar', () => {
  beforeEach(async () => {
    (window as any).__ndwDisableAutoInit = true;
    const mod = await import('../../static/ts-src/app');
    ensureFloatingGenerate = mod.__ndwTestEnsureFloatingGenerate;
    setBodyMode = mod.__ndwTestSetBodyMode;
    window.localStorage.clear();
    document.body.className = '';
    document.body.innerHTML = `
      <div id="appMain"></div>
      <div id="landingFallback" hidden></div>
      <div id="ndwTestPreviewDock" hidden></div>
    `;
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
    expect(wrap).not.toBeNull();
    expect(counterCard).not.toBeNull();
    expect(counterCard?.contains(wrap as Node)).toBe(false);
    expect(document.getElementById('floatingGenerate')).not.toBeNull();
    expect(document.getElementById('generationModeWrap')).toBeNull();
    expect(document.querySelector('[data-quality-mode]')).toBeNull();
  });

  it('keeps generated controls stable across remounts', () => {
    setBodyMode('generated');
    ensureFloatingGenerate();
    const firstButton = document.getElementById('floatingGenerate');
    expect(firstButton).not.toBeNull();

    document.getElementById('floatingGenerateWrap')?.remove();
    ensureFloatingGenerate();

    expect(document.getElementById('floatingGenerate')).not.toBeNull();
    expect(document.getElementById('generationModeWrap')).toBeNull();
    expect(window.localStorage.getItem('ndw_generation_quality')).toBeNull();
  });
});
