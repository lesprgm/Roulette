/**
 * 3D Infinite Tunnel Hero for NDW
 *
 * This module creates an infinite scrolling 3D tunnel using Three.js.
 * Site previews from the prefetch queue float as clickable cards within the tunnel.
 * Object pooling is used for performance - segments are recycled as you scroll.
 */
import * as THREE from 'three';
// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────
// Box Tunnel Dimensions Use (Delphi Reference)
const TUNNEL_WIDTH = 24;
const TUNNEL_HEIGHT = 16;
const SEGMENT_DEPTH = 6;
const NUM_SEGMENTS = 14;
// Grid Divisions
const FLOOR_COLS = 6; // Floor/Ceiling
const WALL_ROWS = 4; // Walls
// Derived Dimensions
const COL_WIDTH = TUNNEL_WIDTH / FLOOR_COLS;
const ROW_HEIGHT = TUNNEL_HEIGHT / WALL_ROWS;
const SCROLL_SPEED = 0.05;
const LERP_FACTOR = 0.1;
const SCROLL_BASE_MULTIPLIER = 120;
const SCROLL_EXTEND_MULTIPLIER = 60;
const SCROLL_EXTEND_THRESHOLD = 0.08;
const PULSE_SPEED = 1.2;
const PULSE_AMPLITUDE = 0.035;
const HOVER_SCALE = 1.15;
const BASE_OPACITY = 0.75;
const HOVER_OPACITY = 0.98;
const HOVER_COLOR_MIX = 0.35;
const FOG_DEPTH_MULTIPLIER = 1.2;
const FOG_START_RATIO = 0.4;
const BASE_FOV = 70;
const FOV_MIN = 66;
const FOV_MAX = 76;
const FOV_LERP = 0.08;
const FOV_VELOCITY_SCALE = 0.08;
// ─────────────────────────────────────────────────────────────────────────────
// Main Class
// ─────────────────────────────────────────────────────────────────────────────
export class InfiniteTunnel {
    scene;
    camera;
    renderer;
    segments = [];
    scrollPos = 0;
    scrollRange = 0;
    scrollMinHeight = 0;
    currentCameraZ = 0;
    previews = [];
    previewFingerprint = '';
    previewById = new Map();
    refreshTimer = null;
    visibilityHandler = null;
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    hoverColor = new THREE.Color(0xffffff);
    scratchColor = new THREE.Color();
    container;
    animationId = 0;
    isDarkMode = false;
    onCardClick = null;
    lastScrollPos = 0;
    fovVelocity = 0;
    rngSeedOffset = 0x9e3779b9;
    assignmentsBySegmentIndex = new Map();
    placeholderPreviews = [
        { id: 'placeholder:0', title: 'Queue warming...', category: 'placeholder', vibe: 'warming', created_at: 0 },
        { id: 'placeholder:1', title: 'Generating previews...', category: 'placeholder', vibe: 'warming', created_at: 0 },
        { id: 'placeholder:2', title: 'Spinning up worlds...', category: 'placeholder', vibe: 'warming', created_at: 0 },
        { id: 'placeholder:3', title: 'Synthesizing scenes...', category: 'placeholder', vibe: 'warming', created_at: 0 },
        { id: 'placeholder:4', title: 'Hold tight...', category: 'placeholder', vibe: 'warming', created_at: 0 }
    ];
    constructor(container) {
        this.container = container;
        // Scene
        this.scene = new THREE.Scene();
        this.setTheme(this.isDarkMode);
        // Camera
        this.camera = new THREE.PerspectiveCamera(BASE_FOV, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(0, 0, 0);
        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
            powerPreference: "high-performance"
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.appendChild(this.renderer.domElement);
        // Events
        window.addEventListener('scroll', this.handleScroll, { passive: true });
        window.addEventListener('resize', this.handleResize);
        window.addEventListener('click', this.handleClick);
        window.addEventListener('pointermove', this.handlePointerMove, { passive: true });
    }
    // ───────────────────────────────────────────────────────────────────────────
    // Initialization
    // ───────────────────────────────────────────────────────────────────────────
    async init() {
        // Fetch previews from backend
        await this.fetchPreviews();
        // Create tunnel segments
        for (let i = 0; i < NUM_SEGMENTS; i++) {
            const segment = this.createSegment(i);
            segment.position.z = -i * SEGMENT_DEPTH;
            this.segments.push(segment);
            this.scene.add(segment);
        }
        // Ensure scroll range for landing page
        this.ensureScrollRange();
        // Start preview refresh loop
        this.startRefreshLoop();
        // Start render loop
        this.animate();
    }
    async fetchPreviews() {
        try {
            const resp = await fetch('/api/prefetch/previews?limit=50', { cache: 'no-store' });
            if (resp.ok) {
                const next = await resp.json();
                if (Array.isArray(next)) {
                    const raw = next;
                    const usePlaceholders = raw.length === 0;
                    const previews = usePlaceholders ? this.placeholderPreviews : raw;
                    const ids = previews.map((item) => String(item?.id ?? '')).filter(Boolean);
                    const sortedIds = [...ids].sort().join('|');
                    const fingerprint = usePlaceholders
                        ? `placeholder:${sortedIds}`
                        : `live:${ids.length}:${sortedIds}`;
                    const changed = fingerprint !== this.previewFingerprint;
                    this.previewFingerprint = fingerprint;
                    this.previews = previews;
                    this.previewById = new Map(this.previews.map(preview => [preview.id, preview]));
                    if (changed) {
                        this.assignmentsBySegmentIndex.clear();
                        return true;
                    }
                    return false;
                }
            }
        }
        catch (e) {
            console.warn('[Tunnel] Failed to fetch previews:', e);
        }
        return false;
    }
    refreshCards() {
        this.segments.forEach(seg => {
            this.populateCards(seg, Math.floor(Math.abs(seg.position.z) / SEGMENT_DEPTH));
        });
    }
    seededRandom(seed) {
        let x = (seed | 0) ^ this.rngSeedOffset;
        x ^= x << 13;
        x ^= x >>> 17;
        x ^= x << 5;
        return (x >>> 0) / 4294967296;
    }
    shouldPlaceCard(segmentIndex, slotId, threshold) {
        const seed = (segmentIndex + 1) * 73856093 ^ (slotId + 1) * 19349663;
        return this.seededRandom(seed) > threshold;
    }
    isDocumentVisible() {
        if (typeof document.visibilityState === 'string') {
            return document.visibilityState === 'visible';
        }
        return !document.hidden;
    }
    startRefreshLoop() {
        if (!this.visibilityHandler) {
            this.visibilityHandler = () => {
                if (this.isDocumentVisible()) {
                    this.startRefreshLoop();
                }
                else {
                    this.stopRefreshLoop();
                }
            };
            document.addEventListener('visibilitychange', this.visibilityHandler);
        }
        if (this.refreshTimer !== null) {
            window.clearInterval(this.refreshTimer);
        }
        if (!this.isDocumentVisible()) {
            return;
        }
        this.refreshTimer = window.setInterval(async () => {
            if (!this.isLandingActive())
                return;
            if (!this.isDocumentVisible())
                return;
            const changed = await this.fetchPreviews();
            if (changed) {
                this.refreshCards();
            }
        }, 5000);
    }
    stopRefreshLoop() {
        if (this.refreshTimer !== null) {
            window.clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    // ───────────────────────────────────────────────────────────────────────────
    // Segment Creation (Object Pool Pattern)
    // ───────────────────────────────────────────────────────────────────────────
    createSegment(index) {
        const group = new THREE.Group();
        const w = TUNNEL_WIDTH / 2;
        const h = TUNNEL_HEIGHT / 2;
        const d = SEGMENT_DEPTH;
        // Grid Material (Color updated by setTheme)
        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x555555,
            transparent: true,
            opacity: 0.35
        });
        const vertices = [];
        // A. Longitudinal Lines (Z-axis) inside the box
        // Floor & Ceiling (varying X)
        for (let i = 0; i <= FLOOR_COLS; i++) {
            const x = -w + (i * COL_WIDTH);
            // Floor
            vertices.push(x, -h, 0, x, -h, -d);
            // Ceiling
            vertices.push(x, h, 0, x, h, -d);
        }
        // Walls (varying Y) - excluding corners already covered
        for (let i = 1; i < WALL_ROWS; i++) {
            const y = -h + (i * ROW_HEIGHT);
            // Left Wall
            vertices.push(-w, y, 0, -w, y, -d);
            // Right Wall
            vertices.push(w, y, 0, w, y, -d);
        }
        // B. Latitudinal Lines (Ring at z=0)
        // Floor, Ceiling, Left Wall, Right Wall edges at current Z slice
        vertices.push(-w, -h, 0, w, -h, 0, // Floor Crossbar
        -w, h, 0, w, h, 0, // Ceiling Crossbar
        -w, -h, 0, -w, h, 0, // Left Wall Crossbar
        w, -h, 0, w, h, 0 // Right Wall Crossbar
        );
        const lineGeo = new THREE.BufferGeometry();
        lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        const lines = new THREE.LineSegments(lineGeo, lineMaterial);
        lines.name = 'grid';
        group.add(lines);
        // Populate Content
        this.populateCards(group, index);
        return group;
    }
    populateCards(segment, segmentIndex, resetAssignments = false) {
        // Cleanup old cards
        const toRemove = [];
        segment.traverse((child) => { if (child.name === 'card')
            toRemove.push(child); });
        toRemove.forEach(obj => {
            segment.remove(obj);
            if (obj.geometry)
                obj.geometry.dispose();
            if (obj.material)
                obj.material.dispose();
        });
        // Populate New Cards (Planar Placement)
        if (this.previews.length === 0)
            return;
        if (this.previewById.size === 0) {
            this.previewById = new Map(this.previews.map(preview => [preview.id, preview]));
        }
        const w = TUNNEL_WIDTH / 2;
        const h = TUNNEL_HEIGHT / 2;
        const d = SEGMENT_DEPTH;
        let assignments = this.assignmentsBySegmentIndex.get(segmentIndex);
        if (!assignments || resetAssignments) {
            assignments = {};
            this.assignmentsBySegmentIndex.set(segmentIndex, assignments);
        }
        // Helper to add card
        const addCard = (pos, rot, width, height, seedIdx, slotId) => {
            const key = String(slotId);
            let preview = this.previewById.get(assignments[key] || '');
            if (!preview) {
                const previewIdx = (segmentIndex * 7 + seedIdx) % this.previews.length;
                preview = this.previews[previewIdx];
                assignments[key] = preview.id;
            }
            const pulseSeed = (segmentIndex + 1) * 83492791 ^ (slotId + 1) * 2654435761;
            const card = this.createCard(preview, width, height, pulseSeed);
            card.position.copy(pos);
            card.rotation.copy(rot);
            segment.add(card);
        };
        // Probabilistic Filling with "Gaps" (similar to Delphi)
        const cellMargin = 0.4;
        // Floor
        for (let i = 0; i < FLOOR_COLS; i++) {
            // Deterministic fill to avoid shuffling on refresh
            if (this.shouldPlaceCard(segmentIndex, i, 0.8)) {
                const x = -w + i * COL_WIDTH + COL_WIDTH / 2;
                addCard(new THREE.Vector3(x, -h + 0.05, -d / 2), // Slightly raised
                new THREE.Euler(-Math.PI / 2, 0, 0), COL_WIDTH - cellMargin, d - cellMargin, i, i);
            }
        }
        // Left Wall
        for (let i = 0; i < WALL_ROWS; i++) {
            const slotId = i + 100;
            if (this.shouldPlaceCard(segmentIndex, slotId, 0.8)) {
                const y = -h + i * ROW_HEIGHT + ROW_HEIGHT / 2;
                addCard(new THREE.Vector3(-w + 0.05, y, -d / 2), new THREE.Euler(0, Math.PI / 2, 0), d - cellMargin, ROW_HEIGHT - cellMargin, slotId, slotId);
            }
        }
        // Right Wall
        for (let i = 0; i < WALL_ROWS; i++) {
            const slotId = i + 200;
            if (this.shouldPlaceCard(segmentIndex, slotId, 0.8)) {
                const y = -h + i * ROW_HEIGHT + ROW_HEIGHT / 2;
                addCard(new THREE.Vector3(w - 0.05, y, -d / 2), new THREE.Euler(0, -Math.PI / 2, 0), d - cellMargin, ROW_HEIGHT - cellMargin, slotId, slotId);
            }
        }
        // Ceiling (Sparser)
        for (let i = 0; i < FLOOR_COLS; i++) {
            const slotId = i + 300;
            if (this.shouldPlaceCard(segmentIndex, slotId, 0.9)) {
                const x = -w + i * COL_WIDTH + COL_WIDTH / 2;
                addCard(new THREE.Vector3(x, h - 0.05, -d / 2), new THREE.Euler(Math.PI / 2, 0, 0), COL_WIDTH - cellMargin, d - cellMargin, slotId, slotId);
            }
        }
    }
    createCard(preview, width, height, pulseSeed) {
        const geometry = new THREE.PlaneGeometry(width, height);
        const color = 0x7c3aed;
        const isPlaceholder = preview.id.startsWith('placeholder:');
        const initialOpacity = BASE_OPACITY;
        const material = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: initialOpacity,
            side: THREE.DoubleSide
        });
        const card = new THREE.Mesh(geometry, material);
        card.name = 'card';
        card.userData = {
            queueId: preview.id,
            title: preview.title,
            pulseOffset: this.seededRandom(pulseSeed) * Math.PI * 2,
            baseColor: color,
            opacity: initialOpacity,
            targetOpacity: BASE_OPACITY,
            isPlaceholder
        };
        return card;
    }
    // ───────────────────────────────────────────────────────────────────────────
    // Infinite Scroll Logic (Segment Recycling)
    // ───────────────────────────────────────────────────────────────────────────
    recycleSegments() {
        const cameraZ = this.camera.position.z;
        const tunnelLength = NUM_SEGMENTS * SEGMENT_DEPTH;
        for (const segment of this.segments) {
            const segmentZ = segment.position.z;
            // Segment is behind camera - move to front
            if (segmentZ > cameraZ + SEGMENT_DEPTH) {
                const minZ = Math.min(...this.segments.map(s => s.position.z));
                segment.position.z = minZ - SEGMENT_DEPTH;
                this.populateCards(segment, Math.floor(Math.abs(segment.position.z) / SEGMENT_DEPTH));
            }
            // Segment is too far ahead - move to back (reverse scroll)
            if (segmentZ < cameraZ - tunnelLength - SEGMENT_DEPTH) {
                const maxZ = Math.max(...this.segments.map(s => s.position.z));
                segment.position.z = maxZ + SEGMENT_DEPTH;
                this.populateCards(segment, Math.floor(Math.abs(segment.position.z) / SEGMENT_DEPTH));
            }
        }
    }
    // ───────────────────────────────────────────────────────────────────────────
    // Event Handlers
    // ───────────────────────────────────────────────────────────────────────────
    handleScroll = () => {
        if (!this.isLandingActive()) {
            this.scrollPos = window.scrollY;
            this.lastScrollPos = window.scrollY;
            return;
        }
        this.ensureScrollRange();
        this.extendScrollRangeIfNeeded();
        this.scrollPos = window.scrollY;
    };
    handleResize = () => {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.ensureScrollRange();
    };
    handlePointerMove = (e) => {
        this.pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
        this.pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    handleClick = () => {
        this.raycaster.setFromCamera(this.pointer, this.camera);
        const cards = [];
        this.segments.forEach(seg => {
            seg.traverse((child) => {
                if (child.name === 'card')
                    cards.push(child);
            });
        });
        const intersects = this.raycaster.intersectObjects(cards);
        if (intersects.length > 0) {
            const clickedCard = intersects[0].object;
            if (clickedCard.userData.isPlaceholder) {
                return;
            }
            const queueId = clickedCard.userData.queueId;
            if (queueId && this.onCardClick) {
                this.onCardClick(queueId);
            }
        }
    };
    // ───────────────────────────────────────────────────────────────────────────
    // Render Loop
    // ───────────────────────────────────────────────────────────────────────────
    animate = () => {
        this.animationId = requestAnimationFrame(this.animate);
        const now = performance.now() * 0.001;
        // Smooth camera movement based on scroll
        const targetZ = -this.scrollPos * SCROLL_SPEED;
        this.currentCameraZ += (targetZ - this.currentCameraZ) * LERP_FACTOR;
        this.camera.position.z = this.currentCameraZ;
        const delta = this.scrollPos - this.lastScrollPos;
        this.lastScrollPos = this.scrollPos;
        const velocityTarget = Math.min(FOV_MAX - BASE_FOV, Math.abs(delta) * FOV_VELOCITY_SCALE);
        this.fovVelocity += (velocityTarget - this.fovVelocity) * FOV_LERP;
        const fovTarget = THREE.MathUtils.clamp(BASE_FOV + this.fovVelocity, FOV_MIN, FOV_MAX);
        if (Math.abs(this.camera.fov - fovTarget) > 0.01) {
            this.camera.fov += (fovTarget - this.camera.fov) * FOV_LERP;
            this.camera.updateProjectionMatrix();
        }
        // Recycle segments for infinite effect
        this.recycleSegments();
        // Hover effect - highlight cards near pointer
        this.raycaster.setFromCamera(this.pointer, this.camera);
        const cards = [];
        this.segments.forEach(seg => {
            seg.traverse((child) => {
                if (child.name === 'card') {
                    cards.push(child);
                    const card = child;
                    const mat = card.material;
                    const pulse = 1 + Math.sin(now * PULSE_SPEED + card.userData.pulseOffset) * PULSE_AMPLITUDE;
                    card.scale.setScalar(pulse);
                    const targetOpacity = card.userData.targetOpacity ?? BASE_OPACITY;
                    const currentOpacity = card.userData.opacity ?? BASE_OPACITY;
                    const nextOpacity = currentOpacity + (targetOpacity - currentOpacity) * 0.1;
                    card.userData.opacity = nextOpacity;
                    mat.opacity = nextOpacity;
                    mat.color.setHex(card.userData.baseColor);
                }
            });
        });
        const intersects = this.raycaster.intersectObjects(cards);
        if (intersects.length > 0) {
            const hovered = intersects[0].object;
            const pulse = 1 + Math.sin(now * PULSE_SPEED + hovered.userData.pulseOffset) * PULSE_AMPLITUDE;
            hovered.scale.setScalar(pulse * HOVER_SCALE);
            this.scratchColor.setHex(hovered.userData.baseColor).lerp(this.hoverColor, HOVER_COLOR_MIX);
            hovered.material.color.copy(this.scratchColor);
            hovered.material.opacity = HOVER_OPACITY;
            document.body.style.cursor = hovered.userData.isPlaceholder ? 'default' : 'pointer';
        }
        else {
            document.body.style.cursor = 'default';
        }
        this.renderer.render(this.scene, this.camera);
    };
    // ───────────────────────────────────────────────────────────────────────────
    // Public API
    // ───────────────────────────────────────────────────────────────────────────
    setOnCardClick(callback) {
        this.onCardClick = callback;
    }
    setTheme(dark) {
        this.isDarkMode = dark;
        // Delphi Reference Colors
        const bg = dark ? 0x050505 : 0xffffff;
        const gridColor = dark ? 0x555555 : 0xb0b0b0;
        const gridOpacity = dark ? 0.35 : 0.5;
        if (this.scene) {
            this.scene.background = new THREE.Color(bg);
            const far = SEGMENT_DEPTH * NUM_SEGMENTS * FOG_DEPTH_MULTIPLIER;
            const near = far * FOG_START_RATIO;
            if (!this.scene.fog) {
                this.scene.fog = new THREE.Fog(bg, near, far);
            }
            else {
                const fog = this.scene.fog;
                fog.color.set(bg);
                fog.near = near;
                fog.far = far;
            }
        }
        // Update existing segments
        this.segments.forEach(seg => {
            const grid = seg.getObjectByName('grid');
            if (grid) {
                const mat = grid.material;
                mat.color.setHex(gridColor);
                mat.opacity = gridOpacity;
                mat.needsUpdate = true;
            }
        });
    }
    ensureScrollRange() {
        if (!this.isLandingActive())
            return;
        const viewport = window.innerHeight;
        const baseHeight = viewport * SCROLL_BASE_MULTIPLIER;
        if (this.scrollMinHeight < baseHeight) {
            this.scrollMinHeight = baseHeight;
        }
        document.body.style.minHeight = `${Math.floor(this.scrollMinHeight)}px`;
        const scrollHeight = Math.max(document.body.scrollHeight, this.scrollMinHeight);
        this.scrollRange = Math.max(scrollHeight - viewport, viewport);
    }
    extendScrollRangeIfNeeded() {
        if (!this.isLandingActive())
            return;
        if (!this.scrollRange)
            this.ensureScrollRange();
        const viewport = window.innerHeight;
        const threshold = Math.max(viewport * 6, this.scrollRange * SCROLL_EXTEND_THRESHOLD);
        if (window.scrollY > this.scrollRange - threshold) {
            this.scrollMinHeight += viewport * SCROLL_EXTEND_MULTIPLIER;
            document.body.style.minHeight = `${Math.floor(this.scrollMinHeight)}px`;
            const scrollHeight = Math.max(document.body.scrollHeight, this.scrollMinHeight);
            this.scrollRange = Math.max(scrollHeight - viewport, viewport);
        }
    }
    isLandingActive() {
        return document.body.classList.contains('landing-mode');
    }
    destroy() {
        cancelAnimationFrame(this.animationId);
        this.stopRefreshLoop();
        if (this.visibilityHandler) {
            document.removeEventListener('visibilitychange', this.visibilityHandler);
            this.visibilityHandler = null;
        }
        window.removeEventListener('scroll', this.handleScroll);
        window.removeEventListener('resize', this.handleResize);
        window.removeEventListener('click', this.handleClick);
        window.removeEventListener('pointermove', this.handlePointerMove);
        this.renderer.dispose();
        this.container.removeChild(this.renderer.domElement);
    }
}
