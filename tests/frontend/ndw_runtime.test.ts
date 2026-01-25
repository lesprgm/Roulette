// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import '../../static/ts-src/ndw';

const getNDW = () => (window as any).NDW;

describe('NDW runtime', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    getNDW()?._cleanup?.();
  });

  afterEach(() => {
    getNDW()?._cleanup?.();
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('auto-initializes input listeners on loop', () => {
    const NDW = getNDW();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 1);
    NDW.loop(() => {});

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    expect(NDW.isDown('a')).toBe(true);
  });

  it('init is idempotent for listener registration', () => {
    const NDW = getNDW();
    const addSpy = vi.spyOn(document, 'addEventListener');

    NDW.init();
    const firstCount = NDW._eventListeners.length;
    NDW.init();
    const secondCount = NDW._eventListeners.length;

    expect(secondCount).toBe(firstCount);
    const keydownCalls = addSpy.mock.calls.filter(call => call[0] === 'keydown').length;
    expect(keydownCalls).toBe(1);
  });

  it('cleanup removes input listeners and clears key state', () => {
    const NDW = getNDW();

    NDW.init();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    expect(NDW._keys.has('a')).toBe(true);

    NDW._cleanup();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }));
    expect(NDW._keys.has('b')).toBe(false);
    expect(NDW._eventListeners.length).toBe(0);
  });

  it('loop cancels any prior frame', () => {
    const NDW = getNDW();
    let nextId = 1;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => nextId++);
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});

    NDW.loop(() => {});
    NDW.loop(() => {});

    expect(cancelSpy).toHaveBeenCalledWith(1);
  });

  it('pointer position uses the primary canvas rect', () => {
    const NDW = getNDW();
    NDW.init();
    const canvas = NDW.makeCanvas({ width: 100, height: 100 });
    canvas.getBoundingClientRect = () =>
      ({
        left: 10,
        top: 20,
        width: 100,
        height: 100,
        right: 110,
        bottom: 120,
        x: 10,
        y: 20,
        toJSON: () => {},
      } as DOMRect);

    const EventCtor = (window as any).PointerEvent || MouseEvent;
    const evt = new EventCtor('pointerdown', { clientX: 50, clientY: 70, bubbles: true });
    canvas.dispatchEvent(evt);

    expect(Math.round(NDW.pointer.x)).toBe(40);
    expect(Math.round(NDW.pointer.y)).toBe(50);
  });
});
