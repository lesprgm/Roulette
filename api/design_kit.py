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
        "clean_white_blue":      {"colors": ["#FFFFFF", "#F9FAFB", "#2563EB", "#1A1A1A"]},
        "warm_cream_teal":       {"colors": ["#F5F0EB", "#FAF7F2", "#0D9488", "#2D2A26"]},
        "pure_white_black":      {"colors": ["#FFFFFF", "#F8F8F8", "#111111", "#111111"]},
        "digital_lavender":      {"colors": ["#F5F3FF", "#EDE9FE", "#A78BFA", "#1E1B4B"]},
        "pastel_peach_mint":     {"colors": ["#FFECD2", "#FFF4E6", "#4ADE80", "#2D2A26"]},
        "stripe_purple":         {"colors": ["#FFFFFF", "#F8F8FF", "#635BFF", "#1A1A1A"]},
        "powder_blue_blush":     {"colors": ["#F0F9FF", "#E0F2FE", "#F472B6", "#1E293B"]},
        "cool_grey_indigo":      {"colors": ["#F8FAFC", "#E2E8F0", "#4F46E5", "#0F172A"]},
        "coral_navy":            {"colors": ["#FFF5F3", "#FFE8E3", "#FF6B6B", "#1A1A2E"]},
        "warm_honey":            {"colors": ["#FEFCE8", "#FEF9C3", "#EAB308", "#422006"]},
        "sky_blue_bubblegum":    {"colors": ["#F0F8FF", "#FFFFFF", "#89ABE3", "#1A1A2E"]},
        "muted_rose_forest":     {"colors": ["#FAF5F5", "#F0E8E8", "#5B8C5A", "#1A1A1A"]},
        "mocha_mousse":          {"colors": ["#FAF7F0", "#EDE0D4", "#A47864", "#2D2A26"]},
        "terracotta_sand":       {"colors": ["#FDF8F0", "#F5EBE0", "#C9694A", "#2D2A26"]},
        "navy_gold":             {"colors": ["#FFFFFF", "#F8F9FA", "#003087", "#1A1A2E"]},
        "sage_off_white":        {"colors": ["#FAF7F0", "#F0F5EB", "#8B9E7B", "#2D2A26"]},
        "cream_burgundy":        {"colors": ["#FCF6F5", "#F8F0EF", "#990011", "#1A1A1A"]},
        "slate_peach":           {"colors": ["#F8FAFC", "#F1F5F9", "#F97316", "#334155"]},
        "warm_amber":            {"colors": ["#FFFBEB", "#FEF3C7", "#F59E0B", "#78350F"]},
        "olive_clay":            {"colors": ["#F8F6F0", "#EDE8D8", "#A3B18A", "#2D2A26"]},
        "deep_purple_gold":      {"colors": ["#F8F6FF", "#EDE9FE", "#7C3AED", "#1A1A2E"]},
        "vintage_cream_rust":    {"colors": ["#FDF8F0", "#F0E6D8", "#C94A3C", "#2D2A26"]},
        "charcoal_lime":         {"colors": ["#1F2937", "#374151", "#A3E635", "#F9FAFB"]},
        "deep_navy_cyan":        {"colors": ["#0F172A", "#1E293B", "#38BDF8", "#F8FAFC"]},
        "midnight_rose":         {"colors": ["#020617", "#1E1B4B", "#FB7185", "#F1F5F9"]},
        "charcoal_amber":        {"colors": ["#1C1917", "#292524", "#EA580C", "#FED7AA"]},
        "true_black_neon":       {"colors": ["#0A0A0A", "#1A1A2E", "#22C55E", "#ECFCCB"]},
        "slate_lemon":           {"colors": ["#1E293B", "#334155", "#FACC15", "#F8FAFC"]},
        "night_sky_electric":    {"colors": ["#0F172A", "#1E293B", "#06B6D4", "#F8FAFC"]},
        "charcoal_gold":         {"colors": ["#1C1917", "#292524", "#D4A017", "#FAFAF9"]},
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
