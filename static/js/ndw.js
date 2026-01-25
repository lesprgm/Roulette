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
        _keys: new Set(),
        _prevKeys: new Set(),
        _audioCtx: null,
        _shake: { x: 0, y: 0, t: 0, intensity: 0 },
        _particles: [],
        _frameId: 0,
        _eventListeners: [],
        _inputInstalled: false,
        _resizeInstalled: false,
        _primaryCanvas: null,
        _trackListener(target, type, handler, options) {
            target.addEventListener(type, handler, options);
            NDW._eventListeners.push({ target, type, handler, options });
        },
        _ensureInit(target) {
            if (!NDW._inputInstalled)
                NDW._installInput(target || document);
            if (!NDW._resizeInstalled)
                NDW._installResize();
            if (!NDW.time.start)
                NDW.time.start = performance.now();
        },
        pointer: { x: 0, y: 0, down: false },
        time: { start: 0, now: 0, elapsed: 0 },
        utils: {
            clamp(v, a, b) { return Math.max(a, Math.min(b, v)); },
            lerp(a, b, t) { return a + (b - a) * t; },
            dist(x1, y1, x2, y2) { return Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2); },
            angle(x1, y1, x2, y2) { return Math.atan2(y2 - y1, x2 - x1); },
            overlaps(a, b) {
                if (!a || !b)
                    return false;
                // Basic AABB or Circle detection
                if (a.radius && b.radius)
                    return NDW.utils.dist(a.x, a.y, b.x, b.y) < (a.radius + b.radius);
                const ax = a.x - (a.width || 0) / 2, ay = a.y - (a.height || 0) / 2;
                const bx = b.x - (b.width || 0) / 2, by = b.y - (b.height || 0) / 2;
                return ax < bx + (b.width || 0) && ax + (a.width || 0) > bx && ay < by + (b.height || 0) && ay + (a.height || 0) > by;
            },
            rng(seed) { let s = (typeof seed === 'number' ? seed : 123456789) | 0; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; s |= 0; return ((s >>> 0) / 4294967296); }; },
            hash(seed) { let x = (seed | 0) ^ 0x9e3779b9; x = Math.imul(x ^ (x >>> 16), 0x85ebca6b); x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35); x ^= x >>> 16; return (x >>> 0) / 4294967296; },
            // Persistence Helpers
            store: {
                get(key) { try {
                    return JSON.parse(localStorage.getItem('ndw_' + key) || 'null');
                }
                catch (_) {
                    return null;
                } },
                set(key, val) { try {
                    localStorage.setItem('ndw_' + key, JSON.stringify(val));
                }
                catch (_) { } },
                clear() { try {
                    Object.keys(localStorage).filter(k => k.startsWith('ndw_')).forEach(k => localStorage.removeItem(k));
                }
                catch (_) { } }
            }
        },
        init(target) {
            NDW._installInput(target || document);
            NDW._installResize();
            NDW.time.start = performance.now();
            return target || document;
        },
        loop(fn) {
            if (typeof fn !== 'function')
                return;
            NDW._ensureInit();
            // Warn if callback doesn't accept dt parameter
            if (fn.length === 0) {
                console.warn('[NDW] loop callback should accept dt parameter for frame-independent timing');
            }
            NDW._tick = fn;
            NDW._last = performance.now();
            if (!NDW._bound)
                NDW._bound = NDW._frame.bind(NDW);
            if (NDW._frameId) {
                cancelAnimationFrame(NDW._frameId);
                NDW._frameId = 0;
            }
            NDW._frameId = requestAnimationFrame(NDW._bound);
        },
        _frame(now) {
            const dt = (now - NDW._last) || 16.6;
            NDW._last = now;
            NDW.time.now = now;
            NDW.time.elapsed = now - NDW.time.start;
            // Update Shake
            if (NDW._shake.t > 0) {
                NDW._shake.t -= dt;
                NDW._shake.x = (Math.random() - 0.5) * NDW._shake.intensity;
                NDW._shake.y = (Math.random() - 0.5) * NDW._shake.intensity;
                const content = document.getElementById('ndw-content');
                if (content)
                    content.style.transform = `translate(${NDW._shake.x}px, ${NDW._shake.y}px)`;
            }
            else {
                const content = document.getElementById('ndw-content');
                if (content && content.style.transform)
                    content.style.transform = '';
            }
            try {
                NDW._tick && NDW._tick(dt);
            }
            catch (e) {
                console.error('[NDW] Loop error:', e);
                if (window.__NDW_showSnippetErrorOverlay)
                    window.__NDW_showSnippetErrorOverlay(e);
            }
            // Sync Keys for isPressed
            NDW._prevKeys.clear();
            NDW._keys.forEach((k) => NDW._prevKeys.add(k));
            NDW._frameId = requestAnimationFrame(NDW._bound);
        },
        // Resource Management: Call this before swapping sites
        _cleanup() {
            // Stop the loop
            if (NDW._frameId) {
                cancelAnimationFrame(NDW._frameId);
                NDW._frameId = 0;
            }
            NDW._tick = null;
            // Clear particles
            NDW._particles = [];
            // Reset shake
            NDW._shake = { x: 0, y: 0, t: 0, intensity: 0 };
            const content = document.getElementById('ndw-content');
            if (content)
                content.style.transform = '';
            // Close audio
            if (NDW._audioCtx) {
                try {
                    NDW._audioCtx.close();
                }
                catch (_) { }
                NDW._audioCtx = null;
            }
            // Drain tracked event listeners
            for (const entry of NDW._eventListeners) {
                try {
                    entry.target.removeEventListener(entry.type, entry.handler, entry.options);
                }
                catch (_) { }
            }
            NDW._eventListeners = [];
            NDW._inputInstalled = false;
            NDW._resizeInstalled = false;
            NDW._resizing = false;
            // Clear handlers
            NDW._keyHandlers = [];
            NDW._ptrHandlers = [];
            NDW._resizeHandlers = [];
            // Clear key state
            NDW._keys.clear();
            NDW._prevKeys.clear();
            NDW._canvases.clear();
            NDW._primaryCanvas = null;
            NDW.pointer = { x: 0, y: 0, down: false };
            // Kill GSAP if present
            if (window.gsap?.killTweensOf) {
                try {
                    window.gsap.killTweensOf('*');
                }
                catch (_) { }
            }
        },
        // Semantic Aliases (Hallucination Resistance)
        jump() { return NDW.isPressed('ArrowUp') || NDW.isPressed(' ') || NDW.isPressed('w') || NDW.isPressed('W'); },
        shot() { return NDW.isPressed('x') || NDW.isPressed('X') || NDW.isPressed('z') || NDW.isPressed('Z') || NDW.isPressed('mouse'); },
        action() { return NDW.isPressed('Enter') || NDW.isPressed(' ') || NDW.isPressed('mouse'); },
        onKey(fn) { NDW._ensureInit(); NDW._keyHandlers.push(fn); },
        onPointer(fn) { NDW._ensureInit(); NDW._ptrHandlers.push(fn); },
        onResize(fn) { NDW._ensureInit(); NDW._resizeHandlers.push(fn); },
        isDown(key) { NDW._ensureInit(); return NDW._keys.has(key); },
        isPressed(key) { NDW._ensureInit(); return NDW._keys.has(key) && !NDW._prevKeys.has(key); },
        makeCanvas(opts) {
            NDW._ensureInit();
            opts = opts || {};
            const parent = typeof opts.parent === 'string' ? document.querySelector(opts.parent) || document.getElementById('ndw-content') || document.body : (opts.parent || document.getElementById('ndw-content') || document.body);
            const c = document.createElement('canvas');
            Object.assign(c.style, { display: 'block', position: 'absolute', top: '0', left: '0' });
            const dpr = Math.max(1, Math.min(3, opts.dpr || window.devicePixelRatio || 1));
            const ctx = c.getContext('2d', { alpha: true, desynchronized: true });
            const _applySize = (wCss, hCss) => {
                c.width = Math.floor(wCss * dpr);
                c.height = Math.floor(hCss * dpr);
                c.style.width = wCss + 'px';
                c.style.height = hCss + 'px';
                try {
                    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                }
                catch (_) { }
            };
            if (opts.fullScreen)
                _applySize(window.innerWidth, window.innerHeight);
            else
                _applySize(opts.width || 800, opts.height || 600);
            parent && parent.appendChild(c);
            NDW._canvases.add(c);
            NDW._primaryCanvas = c;
            c.ctx = ctx;
            c.dpr = dpr;
            c.clear = () => ctx.clearRect(0, 0, c.width / dpr, c.height / dpr);
            // Backward compatibility aliases
            c.element = c;
            c.canvas = c;
            return c;
        },
        resizeCanvasToViewport(canvas, opts) {
            const dpr = opts?.dpr || window.devicePixelRatio || 1;
            canvas.width = window.innerWidth * dpr;
            canvas.height = window.innerHeight * dpr;
            canvas.style.width = '100vw';
            canvas.style.height = '100vh';
            const ctx = canvas.getContext('2d');
            if (ctx)
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            return { width: canvas.width, height: canvas.height, dpr };
        },
        _installInput(scope) {
            if (NDW._inputInstalled)
                return;
            NDW._inputInstalled = true;
            const doc = document;
            const scopeTarget = (scope && typeof scope.addEventListener === 'function') ? scope : doc;
            const resolveCanvas = (e) => {
                const path = e.composedPath?.() || [];
                for (const node of path) {
                    if (node instanceof HTMLCanvasElement)
                        return node;
                }
                let el = e.target;
                while (el) {
                    if (el instanceof HTMLCanvasElement)
                        return el;
                    el = el.parentElement;
                }
                return NDW._primaryCanvas || document.querySelector('#ndw-content canvas') || document.querySelector('canvas');
            };
            const onKeyDown = (e) => { NDW._keys.add(e.key); for (const f of NDW._keyHandlers)
                f(e); };
            const onKeyUp = (e) => { NDW._keys.delete(e.key); for (const f of NDW._keyHandlers)
                f(e); };
            NDW._trackListener(doc, 'keydown', onKeyDown);
            NDW._trackListener(doc, 'keyup', onKeyUp);
            const ptr = (type) => (e) => {
                const canvas = resolveCanvas(e);
                const r = canvas?.getBoundingClientRect() || { left: 0, top: 0 };
                const cx = e.clientX ?? 0;
                const cy = e.clientY ?? 0;
                const p = { type, x: cx - r.left, y: cy - r.top, raw: e, down: NDW.pointer.down };
                NDW.pointer.x = p.x;
                NDW.pointer.y = p.y;
                NDW.pointer.down = (type === 'down' ? true : (type === 'up' ? false : NDW.pointer.down));
                if (type === 'down')
                    NDW._keys.add('mouse');
                else if (type === 'up')
                    NDW._keys.delete('mouse');
                for (const f of NDW._ptrHandlers)
                    f(p);
            };
            NDW._trackListener(scopeTarget, 'pointerdown', ptr('down'));
            NDW._trackListener(doc, 'pointermove', ptr('move'));
            NDW._trackListener(doc, 'pointerup', ptr('up'));
        },
        _installResize() {
            if (NDW._resizeInstalled)
                return;
            NDW._resizeInstalled = true;
            NDW._resizing = true;
            NDW._trackListener(window, 'resize', () => { for (const f of NDW._resizeHandlers)
                f(); });
        },
        audio: {
            playTone(freq = 440, dur = 100, type = 'sine', gain = 0.1) {
                try {
                    if (!NDW._audioCtx)
                        NDW._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    if (NDW._audioCtx.state === 'suspended')
                        NDW._audioCtx.resume();
                    const osc = NDW._audioCtx.createOscillator();
                    const g = NDW._audioCtx.createGain();
                    osc.type = type;
                    osc.frequency.setValueAtTime(freq, NDW._audioCtx.currentTime);
                    g.gain.setValueAtTime(gain, NDW._audioCtx.currentTime);
                    g.gain.exponentialRampToValueAtTime(0.0001, NDW._audioCtx.currentTime + dur / 1000);
                    osc.connect(g);
                    g.connect(NDW._audioCtx.destination);
                    osc.start();
                    osc.stop(NDW._audioCtx.currentTime + dur / 1000);
                }
                catch (_) { }
            }
        },
        juice: {
            shake(intensity = 5, durationMs = 200) { NDW._shake.intensity = intensity; NDW._shake.t = durationMs; }
        },
        particles: {
            spawn(opts) {
                for (let i = 0; i < (opts.count || 1); i++) {
                    NDW._particles.push({
                        x: opts.x, y: opts.y,
                        vx: (Math.random() - 0.5) * (opts.spread || 5),
                        vy: (Math.random() - 0.5) * (opts.spread || 5),
                        life: opts.life || 1000,
                        maxLife: opts.life || 1000,
                        size: opts.size || 3,
                        color: opts.color || '#fff'
                    });
                }
                if (NDW._particles.length > 500)
                    NDW._particles.splice(0, NDW._particles.length - 500);
            },
            update(dt, ctx) {
                for (let i = NDW._particles.length - 1; i >= 0; i--) {
                    const p = NDW._particles[i];
                    p.x += p.vx * (dt / 16);
                    p.y += p.vy * (dt / 16);
                    p.life -= dt;
                    if (p.life <= 0) {
                        NDW._particles.splice(i, 1);
                        continue;
                    }
                    if (ctx) {
                        ctx.fillStyle = p.color;
                        ctx.globalAlpha = p.life / p.maxLife;
                        ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
                        ctx.globalAlpha = 1;
                    }
                }
            }
        }
    };
    global.NDW = NDW;
})(window);
export {};
