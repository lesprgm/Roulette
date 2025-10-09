interface NdwBackground { style?: string; class?: string; }
interface NdwSnippet {
  kind: 'ndw_snippet_v1';
  title?: string;
  html?: string;
  css?: string;
  js?: string;
  background?: NdwBackground;
}
interface FullPageDoc { kind: 'full_page_html'; html: string; }
interface ErrorDoc { error: string; code?: number; }
type NormalizedDoc = NdwSnippet | FullPageDoc | ErrorDoc;

interface NdwPointer { x: number; y: number; down: boolean; type?: string; raw?: Event; }
interface NdwCanvas extends HTMLCanvasElement { ctx: CanvasRenderingContext2D; dpr: number; clear(): void; }

interface NdwRuntime {
  state: Record<string, any>;
  time: { start: number; now: number; elapsed: number };
  pointer: NdwPointer;
  seed(seed: number): void;
  rand(): number;
  loop(tick: (dt: number) => void): void;
  onPointer(fn: (p: NdwPointer) => void): void;
  onKey(fn: (e: KeyboardEvent) => void): void;
  isDown(code: string): boolean;
  onResize(fn: () => void): void;
  makeCanvas(opts?: { fullScreen?: boolean; width?: number; height?: number; parent?: string | HTMLElement; dpr?: number }): NdwCanvas;
  resizeCanvasToViewport(canvas: HTMLCanvasElement, opts?: { dpr?: number }): { width: number; height: number; dpr: number };
  utils: { clamp(v: number, a: number, b: number): number; lerp(a: number, b: number, t: number): number; rng(seed?: number): () => number; };
  audio: { playTone(freq?: number, ms?: number, type?: OscillatorType, gain?: number): void };
}

interface Window { NDW: NdwRuntime; }

declare var NDW: NdwRuntime;
