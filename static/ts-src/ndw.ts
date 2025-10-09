export interface NdwPointer { x:number; y:number; down:boolean; type?:string; raw?:Event; }
export interface NdwTime { start:number; now:number; elapsed:number; }
export interface NdwCanvas extends HTMLCanvasElement { ctx:CanvasRenderingContext2D; dpr:number; clear():void; }
export interface NdwCanvasOpts { fullScreen?:boolean; width?:number; height?:number; parent?:string|HTMLElement; dpr?:number; }
export type NdwLoopFn = (dt:number)=>void;

export interface NdwRuntime {
  state: Record<string,any>;
  time: NdwTime;
  pointer: NdwPointer;
  utils: { clamp:(v:number,a:number,b:number)=>number; lerp:(a:number,b:number,t:number)=>number; rng:(seed?:number)=>()=>number };
  loop(fn:NdwLoopFn):void;
  init(target?:HTMLElement|HTMLCanvasElement|null):HTMLElement|Document;
  onKey(fn:(e:KeyboardEvent)=>void):void;
  onPointer(fn:(p:NdwPointer)=>void):void;
  onResize(fn:()=>void):void;
  isDown(code:string):boolean;
  makeCanvas(opts?:NdwCanvasOpts):NdwCanvas;
  resizeCanvasToViewport(canvas:HTMLCanvasElement, opts?:{dpr?:number}):{width:number;height:number;dpr:number};
  fitCanvasToParent(canvas:HTMLCanvasElement,parent?:HTMLElement):{width:number;height:number;dpr:number};
  audio:{ playTone(freq?:number, durationMs?:number, type?:OscillatorType, gain?:number):void };
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
    pointer: { x:0, y:0, down:false } as NdwPointer,
    time: { start:0, now:0, elapsed:0 } as NdwTime,
    utils: {
      clamp(v:number,a:number,b:number){ return Math.max(a, Math.min(b,v)); },
      lerp(a:number,b:number,t:number){ return a + (b-a)*t; },
      rng(seed?:number){ let s = (typeof seed==='number'?seed:123456789)|0; return ()=>{ s ^= s<<13; s ^= s>>>17; s ^= s<<5; s|=0; return ((s>>>0)/4294967296); }; },
      hash(seed:number){ let x = (seed|0) ^ 0x9e3779b9; x = Math.imul(x ^ (x>>>16), 0x85ebca6b); x = Math.imul(x ^ (x>>>13), 0xc2b2ae35); x ^= x>>>16; return (x>>>0)/4294967296; }
    },
    init(target?:any){
      if (target && target.getContext){
        if (!target.width) target.width = target.clientWidth || 800;
        if (!target.height) target.height = target.clientHeight || 600;
      }
      NDW._installInput(target || document);
      NDW._installResize();
      NDW.time.start = performance.now();
      return target || document;
    },
    loop(fn:NdwLoopFn){
      NDW._tick = fn;
      NDW._last = performance.now();
      if (!NDW._bound) NDW._bound = NDW._frame.bind(NDW);
      requestAnimationFrame(NDW._bound);
    },
    _frame(now:number){
      const dt = (now - NDW._last) || 16.6;
      NDW._last = now;
      NDW.time.now = now;
      NDW.time.elapsed = now - NDW.time.start;
      try { NDW._tick && NDW._tick(dt); } catch(e){ console.error('NDW.tick error', e); }
      requestAnimationFrame(NDW._bound!);
    },
    onKey(fn:(e:KeyboardEvent)=>void){ NDW._keyHandlers.push(fn); },
    onPointer(fn:(p:NdwPointer)=>void){ NDW._ptrHandlers.push(fn); },
    onResize(fn:()=>void){ NDW._resizeHandlers.push(fn); },
    mapCoords(el:HTMLElement, evt:MouseEvent){ const r = el?.getBoundingClientRect?.() || {left:0,top:0}; return { x: evt.clientX - r.left, y: evt.clientY - r.top }; },
    isDown(key:string){ return NDW._keys ? NDW._keys.has(key) : false; },
    makeCanvas(opts?:NdwCanvasOpts){
      opts = opts || {};
      const parent = typeof opts.parent === 'string' ? (document.querySelector(opts.parent) as HTMLElement) || document.getElementById('ndw-app') || document.body : (opts.parent || document.getElementById('ndw-app') || document.body);
      const c = document.createElement('canvas') as NdwCanvas;
      c.style.display = 'block';
      const dpr = Math.max(1, Math.min(3, (opts && opts.dpr) || window.devicePixelRatio || 1));
      const ctx = c.getContext('2d', { alpha: true, desynchronized: true }) as CanvasRenderingContext2D;
      function _applySize(widthCss:number, heightCss:number){
        const w = Math.max(1, Math.floor(widthCss * dpr));
        const h = Math.max(1, Math.floor(heightCss * dpr));
        if (c.width !== w) c.width = w;
        if (c.height !== h) c.height = h;
        c.style.width = widthCss + 'px';
        c.style.height = heightCss + 'px';
        try { ctx.setTransform(dpr,0,0,dpr,0,0); } catch(_) {}
      }
      if (opts.fullScreen) _applySize(window.innerWidth, window.innerHeight); else _applySize(opts.width||800, opts.height||600);
      parent && parent.appendChild(c);
      Object.defineProperty(ctx, 'width', { get(){ return c.width / dpr; } });
      Object.defineProperty(ctx, 'height', { get(){ return c.height / dpr; } });
      c.ctx = ctx; c.dpr = dpr; c.clear = ()=>{ try { ctx.clearRect(0,0,(ctx as any).width,(ctx as any).height); } catch(_) {} };
      return c;
    },
    resizeCanvasToViewport(canvas:HTMLCanvasElement, opts?:{dpr?:number}){
      const dpr = Math.max(1, Math.min(3, (opts && opts.dpr) || window.devicePixelRatio || 1));
      const w = Math.max(1, Math.floor(window.innerWidth * dpr));
      const h = Math.max(1, Math.floor(window.innerHeight * dpr));
      if (canvas.width !== w) canvas.width = w;
      if (canvas.height !== h) canvas.height = h;
      canvas.style.width = '100vw'; canvas.style.height = '100vh';
      try { const ctx = canvas.getContext('2d'); if (ctx) ctx.setTransform(dpr,0,0,dpr,0,0); } catch(_) {}
      return { width:w,height:h,dpr };
    },
    fitCanvasToParent(canvas:HTMLCanvasElement,parent?:HTMLElement){
      parent = parent || canvas.parentElement || document.body;
      const r = parent.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const w = Math.max(1, Math.floor(r.width * dpr));
      const h = Math.max(1, Math.floor(r.height * dpr));
      if (canvas.width !== w) canvas.width = w;
      if (canvas.height !== h) canvas.height = h;
      canvas.style.width = r.width + 'px';
      canvas.style.height = r.height + 'px';
      return { width:w,height:h,dpr };
    },
    _installInput(scope:any){
      const doc = document;
      if (!NDW._keys){
        NDW._keys = new Set<string>();
        doc.addEventListener('keydown', e=>{ NDW._keys.add(e.key); for(const f of NDW._keyHandlers) f(e); });
        doc.addEventListener('keyup', e=>{ NDW._keys.delete(e.key); for(const f of NDW._keyHandlers) f(e); });
      }
      const ptr = (type:string)=>(e:PointerEvent)=>{ const p:NdwPointer={type, x:e.clientX, y:e.clientY, raw:e, down:NDW.pointer.down}; NDW.pointer.x=p.x; NDW.pointer.y=p.y; const wasDown = NDW.pointer.down; NDW.pointer.down = (type==='down'? true : (type==='up'? false : NDW.pointer.down));
        // Mirror pointer state into a pseudo key 'mouse' so snippets can call NDW.isDown('mouse')
        if (!NDW._keys) NDW._keys = new Set<string>();
        if (!wasDown && NDW.pointer.down) NDW._keys.add('mouse');
        if (wasDown && !NDW.pointer.down) NDW._keys.delete('mouse');
        for(const f of NDW._ptrHandlers) f(p); };
      doc.addEventListener('pointerdown', ptr('down'));
      doc.addEventListener('pointermove', ptr('move'));
      doc.addEventListener('pointerup', ptr('up'));
    },
    _installResize(){
      if (NDW._resizing) return; NDW._resizing = true;
      let req = 0; const fire = ()=>{ req=0; for(const f of NDW._resizeHandlers) try{ f(); } catch(e){ console.error('NDW.resize handler error', e); } };
      window.addEventListener('resize', ()=>{ if(!req) req = requestAnimationFrame(fire); });
    },
    audio:{
      _ctx: null as AudioContext | null,
      _ensure(){ if(!this._ctx){ try { this._ctx = new AudioContext(); } catch(_) { this._ctx = null; } } return this._ctx; },
      playTone(freq?:number, durationMs=150, type:OscillatorType='sine', gain=0.02){
        const ctx = this._ensure(); if(!ctx) return;
        const osc = ctx.createOscillator(); const g = ctx.createGain();
        const f = (typeof freq==='number' && !isNaN(freq)) ? freq : 440;
        osc.type = type; osc.frequency.value = Math.max(20, Math.min(8000, f));
        g.gain.value = Math.max(0, Math.min(1, gain));
        osc.connect(g); g.connect(ctx.destination);
        const t0 = ctx.currentTime; osc.start(t0); osc.stop(t0 + Math.max(0.01, durationMs/1000));
      }
    }
  };
  global.NDW = NDW as NdwRuntime;
})(window as any);
