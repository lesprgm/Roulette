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
    "overlays": {
        "noise_grid": {"path": "/static/design-kit/overlays/noise-grid.svg"},
        "mesh_wave": {"path": "/static/design-kit/overlays/mesh-wave.svg"},
        "contour_lines": {"path": "/static/design-kit/overlays/contour-lines.svg"},
        "diagonal_hatch": {"path": "/static/design-kit/overlays/diagonal-hatch.svg"},
        "orbital_dots": {"path": "/static/design-kit/overlays/orbital-dots.svg"},
        "grain_speckle": {"path": "/static/design-kit/overlays/grain-speckle.svg"},
    },
    "background_tokens": {
        "aurora_stage": {
            "overlay": "noise_grid",
            "summary": "Soft sunrise gradients with luminous haze and a faint technical grid.",
        },
        "paper_mesh": {
            "overlay": "mesh_wave",
            "summary": "Editorial mesh backdrop with crisp paper-white spacing and cool accents.",
        },
        "night_grid": {
            "overlay": "contour_lines",
            "summary": "Dark atmospheric stage with contour lines and electric edge highlights.",
        },
        "rose_fog": {
            "overlay": "diagonal_hatch",
            "summary": "Warm rose haze with a lightly printed hatch texture.",
        },
        "festival_dust": {
            "overlay": "orbital_dots",
            "summary": "Playful particle dust over saturated contrast-heavy color fields.",
        },
        "lacquer_shadow": {
            "overlay": "grain_speckle",
            "summary": "Glossy shadow treatment with subtle grain and cinematic darkness.",
        },
    },
    "motion_presets": {
        "parallax_drift": {"summary": "Layered depth with slow counter-moving background planes."},
        "stagger_reveal": {"summary": "GSAP staggered entrance with tight easing and depth blur."},
        "tilt_pointer": {"summary": "Pointer-reactive tilt and highlight response on key surfaces."},
        "scroll_shutter": {"summary": "Large-section scroll transitions with masked reveals."},
        "orbital_float": {"summary": "Ambient floating ornaments orbiting key UI anchors."},
        "kinetic_meter": {"summary": "Animated gauges, rings, and dials tied to user input."},
    },
    "three_starters": {
        "glass_orbit": {"summary": "Reflective orbiting geometry with gentle bloom-style contrast."},
        "particle_ribbon": {"summary": "A ribbon-like field of particles that responds to pointer motion."},
        "terrain_glow": {"summary": "Low-poly terrain waves with luminous accent edges."},
    },
    "palettes": {
        "solar_pop": {"colors": ["#fff7ed", "#fdba74", "#f97316", "#7c2d12"]},
        "mint_signal": {"colors": ["#ecfeff", "#99f6e4", "#14b8a6", "#134e4a"]},
        "midnight_luxe": {"colors": ["#020617", "#1d4ed8", "#38bdf8", "#e0f2fe"]},
        "rose_oxide": {"colors": ["#fff1f2", "#fb7185", "#9f1239", "#4c0519"]},
        "acid_arcade": {"colors": ["#0f172a", "#a3e635", "#facc15", "#f8fafc"]},
        "lavender_fog": {"colors": ["#f5f3ff", "#c4b5fd", "#7c3aed", "#2e1065"]},
    },
    "layouts": {
        "split_lens": {"summary": "Split-screen control and preview layout with asymmetry."},
        "stage_focus": {"summary": "One dominant stage framed by compact utility rails."},
        "bento_magazine": {"summary": "Magazine-like bento grid with uneven card rhythm."},
        "immersive_poster": {"summary": "Full-viewport poster composition with layered foreground controls."},
    },
    "creative_libraries": {
        "gsap_core": {"global": "gsap", "summary": "Local GSAP core for precise timelines and staggered motion."},
        "scroll_trigger": {"global": "ScrollTrigger", "summary": "Local GSAP ScrollTrigger for scroll-tied reveals and parallax."},
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
