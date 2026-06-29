from __future__ import annotations

import hashlib
import random
from typing import Dict, Iterable


ANCHOR_BUCKETS = {
    "material": [
        "concrete",
        "brass",
        "rubber",
        "copper",
        "wood",
        "marble",
        "steel",
        "leather",
        "stone",
        "clay",
        "velvet",
        "wool",
        "silk",
        "glass",
        "ceramic",
        "bamboo",
        "cork",
        "slate",
        "granite",
        "terracotta",
        "bronze",
        "gold",
        "paper",
        "linen",
    ],
    "everyday_object": [
        "typewriter",
        "ticket booth",
        "radio dial",
        "subway map",
        "chess clock",
        "passport stamp",
        "weather vane",
        "library card",
        "vending machine",
        "arcade cabinet",
        "jukebox",
        "photo booth",
        "parking meter",
        "scoreboard",
        "postcard",
    ],
    "layout_metaphor": [
        "route planner",
        "schedule builder",
        "checkout queue",
        "inventory shelf",
        "scoreboard",
        "recipe index",
        "calendar grid",
        "bulletin board",
        "filing cabinet",
        "toolbox",
        "dashboard",
        "shop window",
        "menu board",
        "card catalog",
        "control panel",
        "switchboard",
    ],
    "interaction_verb": [
        "answer",
        "classify",
        "steer",
        "assemble",
        "score",
        "tap",
        "swipe",
        "drag",
        "drop",
        "type",
        "search",
        "select",
        "sort",
        "filter",
        "zoom",
        "scroll",
        "toggle",
        "pinch",
        "rotate",
        "slide",
        "flip",
        "hover",
        "shake",
        "tilt",
        "trace",
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
