// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

let renderDocForPreview: typeof import('../../static/ts-src/app').renderDocForPreview;
let resetTransitions: typeof import('../../static/ts-src/app').__ndwTestResetTransitions;
let originalRAF: typeof window.requestAnimationFrame | undefined;

const tick = () => new Promise(resolve => setTimeout(resolve, 0));

function mockAnimations() {
  const animateSpy = vi.fn(() => ({
    finished: Promise.resolve(),
  }));
  (HTMLElement.prototype as any).animate = animateSpy;
  return animateSpy;
}

describe('NDW transitions', () => {
  beforeEach(async () => {
    (window as any).__ndwDisableAutoInit = true;
    document.body.innerHTML = '<div id="appMain"></div>';
    originalRAF = window.requestAnimationFrame;
    window.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      cb(0);
      return 0 as any;
    }) as typeof window.requestAnimationFrame;
    const mod = await import('../../static/ts-src/app');
    renderDocForPreview = mod.renderDocForPreview;
    resetTransitions = mod.__ndwTestResetTransitions;
    resetTransitions();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    delete (window as any).__ndwDisableAutoInit;
    if (originalRAF) window.requestAnimationFrame = originalRAF;
    vi.restoreAllMocks();
  });

  it('skips transition on first render and applies on second render', async () => {
    const animateSpy = mockAnimations();
    const doc = { kind: 'full_page_html', html: '<!doctype html><html><body><main>One</main></body></html>' };
    const doc2 = { kind: 'full_page_html', html: '<!doctype html><html><body><main>Two</main></body></html>' };

    renderDocForPreview(doc);
    await tick();

    expect(animateSpy).toHaveBeenCalledTimes(0);

    renderDocForPreview(doc2);
    await tick();

    expect(animateSpy).toHaveBeenCalled();
  });

  it('cleans up transition overlays after completion', async () => {
    mockAnimations();
    const doc = { kind: 'full_page_html', html: '<!doctype html><html><body><main>One</main></body></html>' };
    const doc2 = { kind: 'full_page_html', html: '<!doctype html><html><body><main>Two</main></body></html>' };

    renderDocForPreview(doc);
    await tick();
    renderDocForPreview(doc2);
    await tick();
    await tick();

    expect(document.querySelector('.ndw-transition-snapshot')).toBeNull();
    expect(document.querySelector('.ndw-transition-overlay')).toBeNull();
  });

  it('skips transitions when prefers-reduced-motion is set', async () => {
    const animateSpy = mockAnimations();
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) =>
      ({
        matches: query.includes('prefers-reduced-motion'),
        addEventListener: () => {},
        removeEventListener: () => {},
      } as any)) as typeof window.matchMedia;

    const doc = { kind: 'full_page_html', html: '<!doctype html><html><body><main>One</main></body></html>' };
    const doc2 = { kind: 'full_page_html', html: '<!doctype html><html><body><main>Two</main></body></html>' };

    renderDocForPreview(doc);
    await tick();
    renderDocForPreview(doc2);
    await tick();

    expect(animateSpy).toHaveBeenCalledTimes(0);
    window.matchMedia = originalMatchMedia;
  });

  it('rotates transition type across successive renders', async () => {
    const animateSpy = mockAnimations();
    const doc = { kind: 'full_page_html', html: '<!doctype html><html><body><main>One</main></body></html>' };
    const doc2 = { kind: 'full_page_html', html: '<!doctype html><html><body><main>Two</main></body></html>' };
    const doc3 = { kind: 'full_page_html', html: '<!doctype html><html><body><main>Three</main></body></html>' };

    renderDocForPreview(doc);
    await tick();
    renderDocForPreview(doc2);
    await tick();
    renderDocForPreview(doc3);
    await tick();

    // First transition uses portal, second uses iris, so two overlay animations should have different keyframes.
    const overlayCalls = animateSpy.mock.calls.filter((call, idx) => {
      const instance = animateSpy.mock.instances[idx] as HTMLElement | undefined;
      return instance?.classList?.contains('ndw-transition-overlay');
    });
    expect(overlayCalls.length).toBeGreaterThanOrEqual(2);
    const firstOverlayFrames = overlayCalls[0][0] as any[];
    const secondOverlayFrames = overlayCalls[1][0] as any[];
    const firstHasClip = firstOverlayFrames.some(frame => frame.clipPath);
    const secondHasClip = secondOverlayFrames.some(frame => frame.clipPath);
    expect(firstHasClip).toBe(true);
    expect(secondHasClip).toBe(false);
  });
});
