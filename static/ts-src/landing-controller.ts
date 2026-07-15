interface QueuePreview {
  id: string;
  title: string;
  category: string;
  vibe: string;
  created_at: number;
}

type TunnelLike = {
  init: () => Promise<void>;
  setOnCardClick: (callback: (queueId: string) => void) => void;
  setTheme: (dark: boolean) => void;
  destroy: () => void;
};

type LandingControllerOptions = {
  testMode: boolean;
  debugPreviews: boolean;
  onGenerate: (event?: Event) => void;
  onLoadPrefetch: (id: string) => void;
  destroyGeneratedSite: () => void;
};

type LandingWindow = Window & { __ndwLandingCues?: boolean };

export function resolveTunnelCardAction(id: string): 'generate' | 'prefetch' {
  return String(id || '').startsWith('placeholder:') ? 'generate' : 'prefetch';
}

export class LandingController {
  private tunnel: TunnelLike | null = null;
  private previewStatusBound = false;

  constructor(private readonly options: LandingControllerOptions) {}

  bindPreviewStatusEvents(): void {
    if (this.previewStatusBound) return;
    this.previewStatusBound = true;
    const recoveryButton = document.getElementById('landingRecoveryBtn');
    if (recoveryButton) recoveryButton.addEventListener('click', this.options.onGenerate);

    document.getElementById('ndwTestPreviewDock')?.addEventListener('click', event => {
      const button = (event.target as HTMLElement | null)?.closest<HTMLButtonElement>('[data-test-preview-id]');
      const id = button?.dataset.testPreviewId;
      if (id) this.options.onLoadPrefetch(id);
    });

    window.addEventListener('ndw:preview-status', event => {
      const detail = (event as CustomEvent<{ hasLivePreviews?: boolean; previews?: QueuePreview[] }>).detail || {};
      const previews = Array.isArray(detail.previews) ? detail.previews : [];
      this.setFallbackVisible(Boolean(document.body.classList.contains('landing-mode') && !detail.hasLivePreviews));
      this.renderTestPreviewDock(previews);
    });
  }

  async primeTestPreviewStatus(): Promise<void> {
    let previews: QueuePreview[] = [];
    try {
      const response = await fetch('/api/prefetch/previews?limit=6', { cache: 'no-store' });
      if (!response.ok) throw new Error(`preview status failed: ${response.status}`);
      const payload = await response.json();
      previews = Array.isArray(payload) ? payload : [];
    } catch (error) {
      console.warn('[ndw] test preview priming failed', error);
    }
    window.dispatchEvent(new CustomEvent('ndw:preview-status', {
      detail: { hasLivePreviews: previews.length > 0, count: previews.length, previews },
    }));
  }

  hideLandingElements(): void {
    ['.blob-cont', '.noise-overlay', '#cursor-glow'].forEach(selector => document.querySelector(selector)?.remove());
    this.setFallbackVisible(false);
    this.renderTestPreviewDock([]);
    const tunnelContainer = document.getElementById('tunnel-container');
    if (tunnelContainer) tunnelContainer.style.display = 'none';
    this.tunnel?.destroy();
    this.tunnel = null;
    document.body.classList.add('generated-mode');
    document.body.classList.remove('landing-mode');
    document.body.style.removeProperty('min-height');
    document.body.style.removeProperty('background');
    document.body.style.removeProperty('background-image');
    document.body.style.removeProperty('background-color');
    document.documentElement.style.removeProperty('min-height');
  }

  hideHeroOverlay(): void {
    const hero = document.querySelector<HTMLElement>('.hero-wrap');
    if (!hero) return;
    hero.classList.add('is-hidden');
    this.setFallbackVisible(false);
    document.body.classList.remove('landing-mode');
    document.body.classList.add('generated-mode');
  }

  renderLanding(): void {
    this.options.destroyGeneratedSite();
    this.setFallbackVisible(false);
    this.renderTestPreviewDock([]);
    this.lockHeroOverlay();
    this.showHeroOverlay();
    this.ensureSitesCounterOverlay();
    void this.refreshSitesCounter();
    if (this.options.testMode) {
      void this.primeTestPreviewStatus();
    } else {
      void this.initTunnel();
    }
    this.setupLandingCues();
  }

  removeSitesCounterOverlay(): void {
    document.getElementById('sitesCounterFloating')?.remove();
  }

  private setFallbackVisible(visible: boolean): void {
    const fallback = document.getElementById('landingFallback');
    if (!fallback) return;
    fallback.hidden = !visible;
    fallback.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  private renderTestPreviewDock(previews: QueuePreview[]): void {
    const dock = document.getElementById('ndwTestPreviewDock');
    if (!dock) return;
    const livePreviews = this.options.debugPreviews
      ? previews.filter(preview => !String(preview.id || '').startsWith('placeholder:')).slice(0, 4)
      : [];
    dock.hidden = livePreviews.length === 0;
    dock.setAttribute('aria-hidden', livePreviews.length ? 'false' : 'true');
    dock.innerHTML = livePreviews
      .map(preview => `<button type="button" data-test-preview-id="${preview.id}">${preview.title}</button>`)
      .join('');
  }

  private async initTunnel(): Promise<void> {
    const container = document.getElementById('tunnel-container');
    if (!container || this.tunnel) return;
    const { InfiniteTunnel } = await import('./tunnel.js');
    this.tunnel = new InfiniteTunnel(container);
    this.tunnel.setOnCardClick(id => {
      if (resolveTunnelCardAction(id) === 'generate') this.options.onGenerate();
      else this.options.onLoadPrefetch(id);
    });
    await this.tunnel.init();
    this.tunnel.setTheme(false);
  }

  private lockHeroOverlay(): void {
    const hero = document.querySelector<HTMLElement>('.hero-wrap');
    if (!hero) return;
    if (hero.parentElement !== document.body) document.body.appendChild(hero);
    Object.assign(hero.style, {
      position: 'fixed', top: '0', left: '0', width: '100%', height: '100vh', zIndex: '10',
      pointerEvents: 'none', display: 'flex', flexDirection: 'column', justifyContent: 'center',
      alignItems: 'center', textAlign: 'center', transform: 'translateZ(0)', willChange: 'transform',
    });
    const container = hero.querySelector<HTMLElement>('.container');
    if (container) container.style.pointerEvents = 'auto';
  }

  private showHeroOverlay(): void {
    const hero = document.querySelector<HTMLElement>('.hero-wrap');
    if (!hero) return;
    hero.classList.remove('is-hidden');
    document.body.classList.add('landing-mode');
    document.body.classList.remove('generated-mode');
  }

  private setupLandingCues(): void {
    const appWindow = window as LandingWindow;
    if (appWindow.__ndwLandingCues) return;
    const hint = document.getElementById('heroHint');
    const cue = document.getElementById('scrollCue');
    if (!hint && !cue) return;
    appWindow.__ndwLandingCues = true;
    if (this.options.testMode) {
      hint?.classList.remove('is-hidden');
      cue?.classList.remove('is-hidden');
      return;
    }

    function hideAll() {
      if (hintTimer) window.clearTimeout(hintTimer);
      if (cueTimer) window.clearTimeout(cueTimer);
      hint?.classList.add('is-hidden');
      cue?.classList.add('is-hidden');
      window.removeEventListener('scroll', onScroll);
    }
    const onScroll = () => {
      if (window.scrollY > 24) hideAll();
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    const hintTimer = window.setTimeout(() => hint?.classList.add('is-hidden'), 8000);
    const cueTimer = window.setTimeout(() => cue?.classList.add('is-hidden'), 10000);
  }

  private ensureSitesCounterOverlay(): void {
    if (!document.body.classList.contains('landing-mode') || document.getElementById('sitesCounterFloating')) return;
    const wrap = document.createElement('div');
    wrap.id = 'sitesCounterFloating';
    wrap.className = 'ndw-sites-panel';
    wrap.innerHTML = `
      <div id="sitesCounterBadge" class="ndw-sites-badge">Sites generated: —</div>
      <div id="sitesCounterModeMount" class="ndw-sites-mode-mount"></div>
    `;
    document.body.appendChild(wrap);
  }

  private async refreshSitesCounter(): Promise<void> {
    try {
      const response = await fetch(`/metrics/total?ts=${Date.now()}`, {
        headers: { accept: 'application/json' },
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      if (typeof data?.total !== 'number') throw new Error('invalid counter response');
      const badge = document.getElementById('sitesCounterBadge');
      if (badge) badge.textContent = `Sites generated: ${data.total}`;
    } catch (error) {
      console.warn('[ndw] Sites counter unavailable', error);
    }
  }
}
