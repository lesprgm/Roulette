(function (global) {
    if (global.NDW)
        return;
    const NDW = {
        state: {},
        _tick: null,
        _last: 0,
        _bound: null,
        _keyHandlers: [],
        _ptrHandlers: [],
        _resizeHandlers: [],
        _canvases: new Set(),
        pointer: { x: 0, y: 0, down: false },
        time: { start: 0, now: 0, elapsed: 0 },
        utils: {
            clamp(v, a, b) { return Math.max(a, Math.min(b, v)); },
            lerp(a, b, t) { return a + (b - a) * t; },
            rng(seed) { let s = (typeof seed === 'number' ? seed : 123456789) | 0; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; s |= 0; return ((s >>> 0) / 4294967296); }; },
            hash(seed) { let x = (seed | 0) ^ 0x9e3779b9; x = Math.imul(x ^ (x >>> 16), 0x85ebca6b); x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35); x ^= x >>> 16; return (x >>> 0) / 4294967296; }
        },
        init(target) {
            if (target && target.getContext) {
                if (!target.width)
                    target.width = target.clientWidth || 800;
                if (!target.height)
                    target.height = target.clientHeight || 600;
            }
            NDW._installInput(target || document);
            NDW._installResize();
            NDW.time.start = performance.now();
            return target || document;
        },
        loop(fn) {
            if (typeof fn !== 'function') {
                console.error('[NDW] loop requires a function');
                return;
            }
            // Warn if callback doesn't accept dt parameter (common mistake)
            if (fn.length === 0) {
                console.warn('[NDW] Your loop callback should accept dt parameter: NDW.loop((dt) => { ... })');
            }
            NDW._tick = fn;
            NDW._last = performance.now();
            if (!NDW._bound)
                NDW._bound = NDW._frame.bind(NDW);
            requestAnimationFrame(NDW._bound);
        },
        _frame(now) {
            const dt = (now - NDW._last) || 16.6;
            NDW._last = now;
            NDW.time.now = now;
            NDW.time.elapsed = now - NDW.time.start;
            try {
                NDW._tick && NDW._tick(dt);
            }
            catch (e) {
                console.error('[NDW] Loop callback error:', e);
                // Try to show error overlay if available
                if (typeof window.__NDW_showSnippetErrorOverlay === 'function') {
                    window.__NDW_showSnippetErrorOverlay(e);
                }
                // Don't stop the loop; let it continue for debugging
            }
            requestAnimationFrame(NDW._bound);
        },
        onKey(fn) { NDW._keyHandlers.push(fn); },
        onPointer(fn) { NDW._ptrHandlers.push(fn); },
        onResize(fn) { NDW._resizeHandlers.push(fn); },
        mapCoords(el, evt) { const r = el?.getBoundingClientRect?.() || { left: 0, top: 0 }; return { x: evt.clientX - r.left, y: evt.clientY - r.top }; },
        isDown(key) { return NDW._keys ? NDW._keys.has(key) : false; },
        makeCanvas(opts) {
            opts = opts || {};
            const parent = typeof opts.parent === 'string' ? document.querySelector(opts.parent) || document.getElementById('ndw-app') || document.body : (opts.parent || document.getElementById('ndw-app') || document.body);
            const c = document.createElement('canvas');
            c.style.display = 'block';
            c.style.position = 'absolute';
            c.style.top = '0';
            c.style.left = '0';
            const dpr = Math.max(1, Math.min(3, (opts && opts.dpr) || window.devicePixelRatio || 1));
            const ctx = c.getContext('2d', { alpha: true, desynchronized: true });
            function _applySize(widthCss, heightCss) {
                const w = Math.max(1, Math.floor(widthCss * dpr));
                const h = Math.max(1, Math.floor(heightCss * dpr));
                if (c.width !== w)
                    c.width = w;
                if (c.height !== h)
                    c.height = h;
                c.style.width = widthCss + 'px';
                c.style.height = heightCss + 'px';
                try {
                    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                }
                catch (_) { }
            }
            if (opts.fullScreen) {
                _applySize(window.innerWidth, window.innerHeight);
                // Ensure parent can hold positioned canvas
                if (parent && parent.style.position !== 'absolute' && parent.style.position !== 'relative' && parent.style.position !== 'fixed') {
                    parent.style.position = 'relative';
                }
            }
            else {
                _applySize(opts.width || 800, opts.height || 600);
            }
            parent && parent.appendChild(c);
            NDW._canvases.add(c);
            // LLM compatibility aliases to prevent undefined errors
            c.element = c; // some snippets expect canvas.element
            c.canvas = c; // some snippets expect result.canvas
            Object.defineProperty(ctx, 'width', { get() { return c.width / dpr; } });
            Object.defineProperty(ctx, 'height', { get() { return c.height / dpr; } });
            c.ctx = ctx;
            c.dpr = dpr;
            c.clear = () => { try {
                ctx.clearRect(0, 0, ctx.width, ctx.height);
            }
            catch (_) { } };
            // Ensure inputs and resize listeners are installed even if NDW.init isn't called explicitly
            try {
                NDW._installInput(document);
            }
            catch (_) { }
            try {
                NDW._installResize();
            }
            catch (_) { }
            return c;
        },
        resizeCanvasToViewport(canvas, opts) {
            const dpr = Math.max(1, Math.min(3, (opts && opts.dpr) || window.devicePixelRatio || 1));
            const w = Math.max(1, Math.floor(window.innerWidth * dpr));
            const h = Math.max(1, Math.floor(window.innerHeight * dpr));
            if (canvas.width !== w)
                canvas.width = w;
            if (canvas.height !== h)
                canvas.height = h;
            canvas.style.width = '100vw';
            canvas.style.height = '100vh';
            try {
                const ctx = canvas.getContext('2d');
                if (ctx)
                    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            }
            catch (_) { }
            return { width: w, height: h, dpr };
        },
        fitCanvasToParent(canvas, parent) {
            parent = parent || canvas.parentElement || document.body;
            const r = parent.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            const w = Math.max(1, Math.floor(r.width * dpr));
            const h = Math.max(1, Math.floor(r.height * dpr));
            if (canvas.width !== w)
                canvas.width = w;
            if (canvas.height !== h)
                canvas.height = h;
            canvas.style.width = r.width + 'px';
            canvas.style.height = r.height + 'px';
            return { width: w, height: h, dpr };
        },
        _installInput(scope) {
            const doc = document;
            if (!NDW._keys) {
                NDW._keys = new Set();
                doc.addEventListener('keydown', e => { NDW._keys.add(e.key); for (const f of NDW._keyHandlers)
                    f(e); });
                doc.addEventListener('keyup', e => { NDW._keys.delete(e.key); for (const f of NDW._keyHandlers)
                    f(e); });
            }
            const ptr = (type) => (e) => {
                let targetCanvas = null;
                if (NDW._canvases && NDW._canvases.size) {
                    const canvases = Array.from(NDW._canvases.values());
                    for (const canvas of canvases) {
                        if (!canvas.isConnected) {
                            NDW._canvases.delete(canvas);
                            continue;
                        }
                        const rect = canvas.getBoundingClientRect?.();
                        if (rect && e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
                            targetCanvas = canvas;
                            break;
                        }
                    }
                    if (!targetCanvas) {
                        for (const canvas of canvases) {
                            if (canvas.isConnected) {
                                targetCanvas = canvas;
                                break;
                            }
                        }
                    }
                }
                if (!targetCanvas) {
                    targetCanvas = document.querySelector('#ndw-app canvas');
                }
                let px = e.clientX;
                let py = e.clientY;
                if (targetCanvas && targetCanvas.getBoundingClientRect) {
                    const r = targetCanvas.getBoundingClientRect();
                    px = e.clientX - r.left;
                    py = e.clientY - r.top;
                }
                const p = { type, x: px, y: py, raw: e, down: NDW.pointer.down };
                NDW.pointer.x = p.x;
                NDW.pointer.y = p.y;
                const wasDown = NDW.pointer.down;
                NDW.pointer.down = (type === 'down' ? true : (type === 'up' ? false : NDW.pointer.down));
                if (!NDW._keys)
                    NDW._keys = new Set();
                if (!wasDown && NDW.pointer.down)
                    NDW._keys.add('mouse');
                if (wasDown && !NDW.pointer.down)
                    NDW._keys.delete('mouse');
                for (const f of NDW._ptrHandlers)
                    f(p);
            };
            doc.addEventListener('pointerdown', ptr('down'));
            doc.addEventListener('pointermove', ptr('move'));
            doc.addEventListener('pointerup', ptr('up'));
        },
        _installResize() {
            if (NDW._resizing)
                return;
            NDW._resizing = true;
            let req = 0;
            const fire = () => { req = 0; for (const f of NDW._resizeHandlers)
                try {
                    f();
                }
                catch (e) {
                    console.error('NDW.resize handler error', e);
                } };
            window.addEventListener('resize', () => { if (!req)
                req = requestAnimationFrame(fire); });
        },
        audio: {
            playTone(_freq, _durationMs, _type, _gain) { }
        }
    };
    global.NDW = NDW;
})(window);
export {};
