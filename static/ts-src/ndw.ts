export interface NdwPointer { x:number; y:number; down:boolean; type?:string; raw?:Event; }
export interface NdwTime { start:number; now:number; elapsed:number; }
export interface NdwCanvas extends HTMLCanvasElement { ctx:CanvasRenderingContext2D; dpr:number; clear():void; }
export interface NdwCanvasOpts { fullScreen?:boolean; width?:number; height?:number; parent?:string|HTMLElement; dpr?:number; }
export type NdwLoopFn = (dt:number)=>void;

export interface NdwRuntime {
  state: Record<string,any>;
  time: NdwTime;
  pointer: NdwPointer;
  utils: { 
    clamp:(v:number,a:number,b:number)=>number; 
    lerp:(a:number,b:number,t:number)=>number; 
    dist:(x1:number,y1:number,x2:number,y2:number)=>number;
    angle:(x1:number,y1:number,x2:number,y2:number)=>number;
    overlaps:(a:any,b:any)=>boolean;
    rng:(seed?:number)=>()=>number;
    // Persistence Helpers
    store:{ get(key:string):any; set(key:string,val:any):void; clear():void };
  };
  loop(fn:NdwLoopFn):void;
  init(target?:HTMLElement|HTMLCanvasElement|null):HTMLElement|Document;
  onKey(fn:(e:KeyboardEvent)=>void):void;
  onPointer(fn:(p:NdwPointer)=>void):void;
  onResize(fn:()=>void):void;
  isDown(code:string):boolean;
  isPressed(code:string):boolean;
  makeCanvas(opts?:NdwCanvasOpts):NdwCanvas;
  resizeCanvasToViewport(canvas:HTMLCanvasElement, opts?:{dpr?:number}):{width:number;height:number;dpr:number};
  fitCanvasToParent(canvas:HTMLCanvasElement,parent?:HTMLElement):{width:number;height:number;dpr:number};
  audio:{ playTone(freq?:number, durationMs?:number, type?:OscillatorType, gain?:number):void };
  juice:{ shake(intensity?:number, durationMs?:number):void };
  particles:{ spawn(opts:any):void; update(dt:number, ctx?:CanvasRenderingContext2D):void };
  // Resource Management
  _cleanup():void;
  // Semantic Aliases (Hallucination Resistance)
  jump():boolean;
  shot():boolean;
  action():boolean;
}

(function(global: any){
  if (global.NDW) return;
  const NDW: any = {
    state: {},
    _tick: null as NdwLoopFn | null,
    _last: 0,
    _bound: null as FrameRequestCallback | null,
    _keyHandlers: [] as ((e:KeyboardEvent)=>void)[],
    _ptrHandlers: [] as ((p:NdwPointer)=>void)[],
    _resizeHandlers: [] as (()=>void)[],
    _canvases: new Set<HTMLCanvasElement>(),
    _keys: new Set<string>(),
    _prevKeys: new Set<string>(),
    _audioCtx: null as AudioContext | null,
    _shake: { x:0, y:0, t:0, intensity:0 },
    _particles: [] as any[],
    _frameId: 0 as number,
    _eventListeners: [] as { target: EventTarget; type: string; handler: EventListener; options?: boolean | AddEventListenerOptions }[],
    _inputInstalled: false,
    _resizeInstalled: false,
    _primaryCanvas: null as HTMLCanvasElement | null,
    _trackListener(target: EventTarget, type: string, handler: EventListener, options?: boolean | AddEventListenerOptions){
      target.addEventListener(type, handler, options);
      NDW._eventListeners.push({ target, type, handler, options });
    },
    _ensureInit(target?: any){
      if (!NDW._inputInstalled) NDW._installInput(target || document);
      if (!NDW._resizeInstalled) NDW._installResize();
      if (!NDW.time.start) NDW.time.start = performance.now();
    },
    pointer: { x:0, y:0, down:false } as NdwPointer,
    time: { start:0, now:0, elapsed:0 } as NdwTime,
    utils: {
      clamp(v:number,a:number,b:number){ return Math.max(a, Math.min(b,v)); },
      lerp(a:number,b:number,t:number){ return a + (b-a)*t; },
      dist(x1:number,y1:number,x2:number,y2:number){ return Math.sqrt((x2-x1)**2 + (y2-y1)**2); },
      angle(x1:number,y1:number,x2:number,y2:number){ return Math.atan2(y2-y1, x2-x1); },
      overlaps(a:any, b:any){
        if (!a || !b) return false;
        // Basic AABB or Circle detection
        if (a.radius && b.radius) return NDW.utils.dist(a.x,a.y,b.x,b.y) < (a.radius + b.radius);
        const ax = a.x - (a.width||0)/2, ay = a.y - (a.height||0)/2;
        const bx = b.x - (b.width||0)/2, by = b.y - (b.height||0)/2;
        return ax < bx + (b.width||0) && ax + (a.width||0) > bx && ay < by + (b.height||0) && ay + (a.height||0) > by;
      },
      rng(seed?:number){ let s = (typeof seed==='number'?seed:123456789)|0; return ()=>{ s ^= s<<13; s ^= s>>>17; s ^= s<<5; s|=0; return ((s>>>0)/4294967296); }; },
      hash(seed:number){ let x = (seed|0) ^ 0x9e3779b9; x = Math.imul(x ^ (x>>>16), 0x85ebca6b); x = Math.imul(x ^ (x>>>13), 0xc2b2ae35); x ^= x>>>16; return (x>>>0)/4294967296; },
      // Persistence Helpers
      store: {
        get(key:string){ try { return JSON.parse(localStorage.getItem('ndw_'+key) || 'null'); } catch(_) { return null; } },
        set(key:string, val:any){ try { localStorage.setItem('ndw_'+key, JSON.stringify(val)); } catch(_) {} },
        clear(){ try { Object.keys(localStorage).filter(k=>k.startsWith('ndw_')).forEach(k=>localStorage.removeItem(k)); } catch(_) {} }
      }
    },
    init(target?:any){
      NDW._installInput(target || document);
      NDW._installResize();
      NDW.time.start = performance.now();
      return target || document;
    },
    loop(fn:NdwLoopFn){
      if (typeof fn !== 'function') return;
      NDW._ensureInit();
      // Warn if callback doesn't accept dt parameter
      if (fn.length === 0) {
        console.warn('[NDW] loop callback should accept dt parameter for frame-independent timing');
      }
      NDW._tick = fn;
      NDW._last = performance.now();
      if (!NDW._bound) NDW._bound = NDW._frame.bind(NDW);
      if (NDW._frameId) { cancelAnimationFrame(NDW._frameId); NDW._frameId = 0; }
      NDW._frameId = requestAnimationFrame(NDW._bound);
    },
    _frame(now:number){
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
        if (content) content.style.transform = `translate(${NDW._shake.x}px, ${NDW._shake.y}px)`;
      } else {
        const content = document.getElementById('ndw-content');
        if (content && content.style.transform) content.style.transform = '';
      }

      try { 
        NDW._tick && NDW._tick(dt); 
      } catch(e){ 
        console.error('[NDW] Loop error:', e);
        if ((window as any).__NDW_showSnippetErrorOverlay) (window as any).__NDW_showSnippetErrorOverlay(e);
      }

      // Sync Keys for isPressed
      NDW._prevKeys.clear();
      NDW._keys.forEach((k:string) => NDW._prevKeys.add(k));

      NDW._frameId = requestAnimationFrame(NDW._bound!);
    },
    // Resource Management: Call this before swapping sites
    _cleanup(){
      // Stop the loop
      if (NDW._frameId) { cancelAnimationFrame(NDW._frameId); NDW._frameId = 0; }
      NDW._tick = null;
      // Clear particles
      NDW._particles = [];
      // Reset shake
      NDW._shake = { x:0, y:0, t:0, intensity:0 };
      const content = document.getElementById('ndw-content');
      if (content) content.style.transform = '';
      // Close audio
      if (NDW._audioCtx) { try { NDW._audioCtx.close(); } catch(_) {} NDW._audioCtx = null; }
      // Drain tracked event listeners
      for (const entry of NDW._eventListeners) {
        try { entry.target.removeEventListener(entry.type, entry.handler, entry.options); } catch(_) {}
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
      NDW.pointer = { x:0, y:0, down:false } as NdwPointer;
      // Kill GSAP if present
      if ((window as any).gsap?.killTweensOf) { try { (window as any).gsap.killTweensOf('*'); } catch(_) {} }
    },
    // Semantic Aliases (Hallucination Resistance)
    jump(){ return NDW.isPressed('ArrowUp') || NDW.isPressed(' ') || NDW.isPressed('w') || NDW.isPressed('W'); },
    shot(){ return NDW.isPressed('x') || NDW.isPressed('X') || NDW.isPressed('z') || NDW.isPressed('Z') || NDW.isPressed('mouse'); },
    action(){ return NDW.isPressed('Enter') || NDW.isPressed(' ') || NDW.isPressed('mouse'); },
    onKey(fn:(e:KeyboardEvent)=>void){ NDW._ensureInit(); NDW._keyHandlers.push(fn); },
    onPointer(fn:(p:NdwPointer)=>void){ NDW._ensureInit(); NDW._ptrHandlers.push(fn); },
    onResize(fn:()=>void){ NDW._ensureInit(); NDW._resizeHandlers.push(fn); },
    isDown(key:string){ NDW._ensureInit(); return NDW._keys.has(key); },
    isPressed(key:string){ NDW._ensureInit(); return NDW._keys.has(key) && !NDW._prevKeys.has(key); },
    makeCanvas(opts?:NdwCanvasOpts){
      NDW._ensureInit();
      opts = opts || {};
      const parent = typeof opts.parent === 'string' ? (document.querySelector(opts.parent) as HTMLElement) || document.getElementById('ndw-content') || document.body : (opts.parent || document.getElementById('ndw-content') || document.body);
      const c = document.createElement('canvas') as NdwCanvas;
      Object.assign(c.style, { display:'block', position:'absolute', top:'0', left:'0' });
      const dpr = Math.max(1, Math.min(3, opts.dpr || window.devicePixelRatio || 1));
      const ctx = c.getContext('2d', { alpha: true, desynchronized: true }) as CanvasRenderingContext2D;
      const _applySize = (wCss:number, hCss:number)=>{
        c.width = Math.floor(wCss * dpr); c.height = Math.floor(hCss * dpr);
        c.style.width = wCss + 'px'; c.style.height = hCss + 'px';
        try { ctx.setTransform(dpr,0,0,dpr,0,0); } catch(_) {}
      };
      if (opts.fullScreen) _applySize(window.innerWidth, window.innerHeight);
      else _applySize(opts.width||800, opts.height||600);
      parent && parent.appendChild(c);
      NDW._canvases.add(c);
      NDW._primaryCanvas = c;
      c.ctx = ctx; c.dpr = dpr; c.clear = ()=>ctx.clearRect(0,0,c.width/dpr,c.height/dpr);
      // Backward compatibility aliases
      (c as any).element = c;
      (c as any).canvas = c;
      return c;
    },
    resizeCanvasToViewport(canvas:HTMLCanvasElement, opts?:any){
      const dpr = opts?.dpr || window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr; canvas.height = window.innerHeight * dpr;
      canvas.style.width = '100vw'; canvas.style.height = '100vh';
      const ctx = canvas.getContext('2d'); if (ctx) ctx.setTransform(dpr,0,0,dpr,0,0);
      return { width:canvas.width, height:canvas.height, dpr };
    },
    _installInput(scope:any){
      if (NDW._inputInstalled) return;
      NDW._inputInstalled = true;
      const doc = document;
      const scopeTarget = (scope && typeof scope.addEventListener === 'function') ? scope : doc;
      const resolveCanvas = (e: PointerEvent): HTMLCanvasElement | null => {
        const path = (e as any).composedPath?.() || [];
        for (const node of path) {
          if (node instanceof HTMLCanvasElement) return node;
        }
        let el = e.target as Element | null;
        while (el) {
          if (el instanceof HTMLCanvasElement) return el;
          el = el.parentElement;
        }
        return NDW._primaryCanvas || document.querySelector('#ndw-content canvas') || document.querySelector('canvas');
      };
      const onKeyDown = (e: KeyboardEvent) => { NDW._keys.add(e.key); for(const f of NDW._keyHandlers) f(e); };
      const onKeyUp = (e: KeyboardEvent) => { NDW._keys.delete(e.key); for(const f of NDW._keyHandlers) f(e); };
      NDW._trackListener(doc, 'keydown', onKeyDown);
      NDW._trackListener(doc, 'keyup', onKeyUp);
      const ptr = (type:string) => (e:PointerEvent)=>{
        const canvas = resolveCanvas(e);
        const r = canvas?.getBoundingClientRect() || {left:0,top:0};
        const cx = (e as any).clientX ?? 0;
        const cy = (e as any).clientY ?? 0;
        const p:NdwPointer={type, x:cx-r.left, y:cy-r.top, raw:e, down:NDW.pointer.down};
        NDW.pointer.x=p.x; NDW.pointer.y=p.y; NDW.pointer.down = (type==='down'?true:(type==='up'?false:NDW.pointer.down));
        if (type==='down') NDW._keys.add('mouse'); else if (type==='up') NDW._keys.delete('mouse');
        for(const f of NDW._ptrHandlers) f(p);
      };
      NDW._trackListener(scopeTarget, 'pointerdown', ptr('down'));
      NDW._trackListener(doc, 'pointermove', ptr('move'));
      NDW._trackListener(doc, 'pointerup', ptr('up'));
    },
    _installResize(){
      if (NDW._resizeInstalled) return;
      NDW._resizeInstalled = true;
      NDW._resizing = true;
      NDW._trackListener(window, 'resize', ()=>{ for(const f of NDW._resizeHandlers) f(); });
    },
    audio:{
      playTone(freq=440, dur=100, type='sine', gain=0.1){
        try {
          if (!NDW._audioCtx) NDW._audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
          if (NDW._audioCtx.state === 'suspended') NDW._audioCtx.resume();
          const osc = NDW._audioCtx.createOscillator();
          const g = NDW._audioCtx.createGain();
          osc.type = type as OscillatorType;
          osc.frequency.setValueAtTime(freq, NDW._audioCtx.currentTime);
          g.gain.setValueAtTime(gain, NDW._audioCtx.currentTime);
          g.gain.exponentialRampToValueAtTime(0.0001, NDW._audioCtx.currentTime + dur/1000);
          osc.connect(g); g.connect(NDW._audioCtx.destination);
          osc.start(); osc.stop(NDW._audioCtx.currentTime + dur/1000);
        } catch(_) {}
      }
    },
    juice:{
      shake(intensity=5, durationMs=200){ NDW._shake.intensity = intensity; NDW._shake.t = durationMs; }
    },
    particles: {
      spawn(opts: any) {
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
        if (NDW._particles.length > 500) NDW._particles.splice(0, NDW._particles.length - 500);
      },
      update(dt: number, ctx?: CanvasRenderingContext2D) {
        for (let i = NDW._particles.length - 1; i >= 0; i--) {
          const p = NDW._particles[i];
          p.x += p.vx * (dt / 16); p.y += p.vy * (dt / 16);
          p.life -= dt;
          if (p.life <= 0) { NDW._particles.splice(i, 1); continue; }
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
  global.NDW = NDW as NdwRuntime;
})(window as any);
