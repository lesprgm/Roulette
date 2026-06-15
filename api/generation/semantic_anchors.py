from __future__ import annotations

import hashlib
import random
from typing import Dict, Iterable


ANCHOR_BUCKETS = {
    "material": [
        "concrete",
        "brass",
        "paper pulp",
        "smoked glass",
        "ceramic glaze",
        "salt crystal",
        "charcoal",
        "rubber",
        "woven linen",
        "oxidized copper",
        "liquid chrome",
        "translucent resin",
        "ash wood",
        "magnetic sand",
        "frosted acrylic",
    ],
    "natural_phenomenon": [
        "bioluminescence",
        "fog bank",
        "tidal pull",
        "murmuration",
        "mycelium growth",
        "desert mirage",
        "aurora",
        "coral bleaching",
        "glacial calving",
        "lightning filament",
        "rain shadow",
        "thermal vent",
        "seed dispersal",
        "eclipse",
        "magnetic storm",
    ],
    "cultural_object": [
        "typewriter",
        "astrolabe",
        "ticket booth",
        "field notebook",
        "radio dial",
        "loom",
        "cabinet of curiosities",
        "subway map",
        "chess clock",
        "letterpress tray",
        "passport stamp",
        "weather vane",
        "library card",
        "film contact sheet",
        "ceremonial mask",
    ],
    "system_metaphor": [
        "neighborhood directory",
        "garden ecology",
        "traffic choreography",
        "pressure chamber",
        "orbital registry",
        "route planner",
        "machine choir",
        "translation engine",
        "schedule builder",
        "checkout queue",
        "inventory shelf",
        "scoreboard",
        "recipe index",
        "calendar grid",
        "ticket pipeline",
        "match bracket",
    ],
    "interaction_verb": [
        "launch",
        "tune",
        "splice",
        "cultivate",
        "answer",
        "weave",
        "magnetize",
        "classify",
        "steer",
        "race",
        "scrub",
        "assemble",
        "score",
        "illuminate",
        "trade",
    ],
}


def _stable_int(parts: Iterable[str]) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def select_semantic_anchors(seed: int | None = None, cell_key: str = "") -> Dict[str, str]:
    rng = random.Random(_stable_int([seed or 0, cell_key or "default"]))
    anchors: Dict[str, str] = {}
    for bucket, values in ANCHOR_BUCKETS.items():
        anchors[bucket] = values[rng.randrange(len(values))]
    return anchors
