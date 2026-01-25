// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { InfiniteTunnel } from '../../static/ts-src/tunnel';

describe('Tunnel refresh loop', () => {
  let intervalFn: (() => Promise<void>) | null = null;
  let originalFetch: typeof fetch | undefined;

  beforeEach(() => {
    document.body.innerHTML = '<div data-role="hero"></div><div id="tunnel-container"></div>';
    document.body.className = 'landing-mode';
    intervalFn = null;
    originalFetch = globalThis.fetch;
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 0);
    vi.spyOn(window, 'setInterval').mockImplementation((fn: TimerHandler) => {
      intervalFn = fn as () => Promise<void>;
      return 1 as unknown as number;
    });
    vi.spyOn(window, 'clearInterval').mockImplementation(() => {});
    vi.spyOn(Math, 'random').mockReturnValue(0.95);

    let call = 0;
    const fetchMock = vi.fn(async () => {
      call += 1;
      const payload =
        call <= 2
          ? [{ id: 'file:a.json', title: 'A', category: 'x', vibe: 'y', created_at: 1 }]
          : [
              { id: 'file:a.json', title: 'A', category: 'x', vibe: 'y', created_at: 1 },
              { id: 'file:b.json', title: 'B', category: 'x', vibe: 'y', created_at: 2 },
            ];
      return {
        ok: true,
        json: async () => payload,
      };
    });
    (globalThis as any).fetch = fetchMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    }
    document.body.innerHTML = '';
  });

  it('polls previews and repopulates when queue changes', async () => {
    const container = document.getElementById('tunnel-container') as HTMLElement;
    const tunnel = new InfiniteTunnel(container);
    await tunnel.init();

    expect(intervalFn).toBeTypeOf('function');

    const segments = (tunnel as any).segments as any[];
    const countCards = () => {
      let count = 0;
      segments.forEach(seg => {
        seg.traverse((child: any) => {
          if (child?.name === 'card') count += 1;
        });
      });
      return count;
    };

    const initialCount = countCards();
    expect(initialCount).toBeGreaterThan(0);

    if (intervalFn) await intervalFn();
    const sameCount = countCards();
    expect(sameCount).toBe(initialCount);

    if (intervalFn) await intervalFn();
    const changedCount = countCards();
    expect(changedCount).toBeGreaterThanOrEqual(initialCount);
  });
});
