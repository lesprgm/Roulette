from __future__ import annotations

import json
from typing import Any, Dict


DESIGN_KIT_MANIFEST: Dict[str, Dict[str, Dict[str, Any]]] = {
    "fonts": {
        "display_orbit": {
            "family": "var(--ndw-font-display-orbit)",
            "sample": "A wide geometric display stack for bold hero moments.",
        },
        "display_editorial": {
            "family": "var(--ndw-font-display-editorial)",
            "sample": "A serif-forward editorial stack for elegant, atmospheric layouts.",
        },
        "display_grotesk": {
            "family": "var(--ndw-font-display-grotesk)",
            "sample": "A neutral grotesk stack for crisp product and dashboard typography.",
        },
        "body_clean": {
            "family": "var(--ndw-font-body-clean)",
            "sample": "A clean UI stack for readable controls and dense tools.",
        },
        "body_soft": {
            "family": "var(--ndw-font-body-soft)",
            "sample": "A warmer body stack for playful and narrative experiences.",
        },
    },
    "motion_presets": {
        "parallax_drift": {"summary": "Layered depth with slow counter-moving background planes."},
        "stagger_reveal": {"summary": "GSAP staggered entrance with tight easing and depth blur."},
        "tilt_pointer": {"summary": "Pointer-reactive tilt and highlight response on key surfaces."},
        "scroll_shutter": {"summary": "Large-section scroll transitions with masked reveals."},
        "orbital_float": {"summary": "Ambient floating ornaments orbiting key UI anchors."},
        "kinetic_meter": {"summary": "Animated gauges, rings, and dials tied to user input."},
        "cursor_glow_trail": {"summary": "Pointer-reactive glow trail that follows the cursor with soft falloff."},
        "float_in_sequence": {"summary": "Sequential floating entrance with soft bounce and staggered delays."},
        "morph_surface": {"summary": "SVG or background shape morphing transitions between states."},
        "pulse_ring": {"summary": "Expanding ring pulse effect on hover, click, or state change."},
        "shimmer_sweep": {"summary": "Metallic or glass shimmer that sweeps diagonally across a surface."},
        "count_rollup": {"summary": "Animated number rollup for counters, scores, and stat displays."},
        "accordion_spring": {"summary": "Springy expand and collapse with elastic overshoot at endpoints."},
        "wiggle_alert": {"summary": "Quick wiggle or shake animation for alerts, errors, and invalid inputs."},
    },
    "three_starters": {
        "glass_orbit": {"summary": "Reflective orbiting geometry with gentle bloom-style contrast."},
        "particle_ribbon": {"summary": "A ribbon-like field of particles that responds to pointer motion."},
        "terrain_glow": {"summary": "Low-poly terrain ridges with luminous accent edges."},
    },
    "palettes": {
        "solar_pop": {"colors": ["#fff7ed", "#fdba74", "#f97316", "#7c2d12"]},
        "mint_signal": {"colors": ["#ecfeff", "#99f6e4", "#14b8a6", "#134e4a"]},
        "midnight_luxe": {"colors": ["#020617", "#1d4ed8", "#38bdf8", "#e0f2fe"]},
        "rose_oxide": {"colors": ["#fff1f2", "#fb7185", "#9f1239", "#4c0519"]},
        "acid_arcade": {"colors": ["#0f172a", "#a3e635", "#facc15", "#f8fafc"]},
        "lavender_fog": {"colors": ["#f5f3ff", "#c4b5fd", "#7c3aed", "#2e1065"]},
        "ember_dusk": {"colors": ["#1c1917", "#292524", "#ea580c", "#fed7aa"]},
        "cyber_lime": {"colors": ["#0a0a0a", "#1a1a2e", "#a3e635", "#ecfccb"]},
        "ocean_deep": {"colors": ["#020617", "#0f766e", "#67e8f9", "#cffafe"]},
        "candy_pop": {"colors": ["#fdf2f8", "#fbcfe8", "#ec4899", "#831843"]},
        "concrete_minimal": {"colors": ["#f8fafc", "#cbd5e1", "#475569", "#0f172a"]},
        "blush_wine": {"colors": ["#fef2f2", "#e11d48", "#881337", "#450a0a"]},
        "forest_moss": {"colors": ["#f0fdf4", "#4ade80", "#15803d", "#052e16"]},
        "sunset_neon": {"colors": ["#0f172a", "#f97316", "#d946ef", "#fef9c3"]},
    },
    "layouts": {
        "split_lens": {"summary": "Split-screen control and preview layout with asymmetry."},
        "stage_focus": {"summary": "One dominant stage framed by compact utility rails."},
        "bento_magazine": {"summary": "Magazine-like bento grid with uneven card rhythm."},
        "immersive_poster": {"summary": "Full-viewport poster composition with layered foreground controls."},
        "card_grid": {"summary": "Responsive card-based grid with balanced whitespace and hover states."},
        "sidebar_shell": {"summary": "Persistent vertical sidebar with dynamic main content area."},
        "vertical_narrative": {"summary": "Long-scroll single-column layout with sequential section reveals."},
        "canvas_hud": {"summary": "Full-window canvas stage with floating overlay controls."},
        "tabbed_workspace": {"summary": "Multi-panel tabbed interface with collapsible side panels."},
        "hero_centered": {"summary": "Bold centered headline and CTA with minimal UI, often over a full-width visual."},
        "masonry_waterfall": {"summary": "Variable-height waterfall card grid optimized for visual browsing."},
        "single_column": {"summary": "Stacked single-column with distinct header, content sections, and footer."},
        "z_pattern_landing": {"summary": "Content arranged along a Z-shaped scanning path from headline to visual to CTA."},
        "gallery_showcase": {"summary": "Full-bleed grid of visual thumbnails with overlay text and lightbox style."},
    },
    "creative_libraries": {
        "ndw_runtime": {
            "global": "NDW",
            "summary": "Local game/creative runtime for canvas loops, pointer/keyboard state, seeded RNG, particles, shake, tones, and simple persistence.",
        },
        "gsap_core": {"global": "gsap", "summary": "Local GSAP core for precise timelines, staggered motion, state transitions, score/result reveals, and interface choreography."},
        "lucide_icons": {"global": "lucide", "summary": "Local icon set for app/workspace chrome, controls, toolbars, cards, and legible UI affordances."},
        "alpine_state": {
            "global": "Alpine",
            "script": "/static/vendor/alpine.min.js",
            "summary": "Local Alpine.js for declarative UI state in apps, commerce flows, forms, drawers, filters, carts, quizzes, and multi-step workflows.",
        },
        "matter_physics": {
            "global": "Matter",
            "script": "/static/vendor/matter.min.js",
            "summary": "Local Matter.js for 2D physics games and toys such as pinball, pachinko, stacking, marble, basket, and block-drop mechanics.",
        },
        "three_orbit_controls": {
            "import": "three/addons/controls/OrbitControls.js",
            "summary": "Local OrbitControls addon for explorable 3D scenes.",
        },
        "three_bloom_pipeline": {
            "imports": [
                "three/addons/postprocessing/EffectComposer.js",
                "three/addons/postprocessing/RenderPass.js",
                "three/addons/postprocessing/UnrealBloomPass.js",
            ],
            "summary": "Local postprocessing pipeline for restrained glow/bloom effects.",
        },
    },
    "library_profiles": {
        "ndw_canvas_game_loop": {"summary": "Use NDW.makeCanvas, NDW.loop, keyboard/pointer helpers, score state, and reset/replay for lightweight games."},
        "ndw_audio_particles": {"summary": "Use NDW.loop plus NDW.audio.playTone, NDW.particles.spawn, and NDW.juice.shake for game-feel feedback."},
        "gsap_timeline_dom": {"summary": "Use GSAP timelines for DOM-based entrances, staged transitions, and focused interaction response."},
        "gsap_state_transition": {"summary": "Use GSAP to animate state changes such as card flips, score updates, filters, saved states, and results."},
        "lucide_app_chrome": {"summary": "Use Lucide icons to make SaaS, commerce, booking, and tool interfaces feel like real usable apps."},
        "alpine_ui_state": {"summary": "Use Alpine.js for app/tool/commerce UI state: filters, forms, carts, accordions, drawers, tabs, selected records, and multi-step flows."},
        "matter_physics_game": {"summary": "Use Matter.js for physics-first games and toys with collisions, gravity, constraints, scoring, reset, and visible cause/effect."},
        "three_orbit_scene": {"summary": "Use Three.js plus OrbitControls for explorable objects, maps, instruments, or spatial demos."},
        "three_bloom_scene": {"summary": "Use Three.js postprocessing only for one restrained focal scene, not as generic neon decoration."},
        "dom_css_state_machine": {"summary": "Use DOM/CSS state, CSS grid, buttons, forms, outputs, and accessible controls for puzzle/app flows."},
    },
    "composition_recipes": {
        "fictional_instrument": {"summary": "A playable visual instrument with controls that reshape the scene."},
        "living_poster": {"summary": "A poster-like composition that breathes and reacts through layered motion."},
        "spatial_map": {"summary": "A navigable map or field with labels, depth, and a signature control."},
        "kinetic_editorial": {"summary": "Magazine typography with scroll-linked shutters and dramatic reveals."},
        "artifact_simulator": {"summary": "A fictional object/product simulator with tactile calibration UI."},
        "civic_machine": {"summary": "A weird institutional system with forms, counters, seals, and procedural motion."},
        "botanical_lab": {"summary": "Organic growth, sensor panels, and living material textures."},
        "weather_console": {"summary": "Atmospheric controls that reshape clouds, particles, gradients, or maps."},
    },
}


def compact_design_kit_manifest() -> str:
    return json.dumps(DESIGN_KIT_MANIFEST, separators=(",", ":"), ensure_ascii=True)
