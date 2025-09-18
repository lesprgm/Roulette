Return ONE JSON object that validates against my schema for a Page.

Rules:
- Output JSON only. No prose, markdown, or comments.
- Contract (required keys): components[], layout, palette, links, seed (int), model_version (string).
- For components: each item must have id, type ∈ {hero, card, cta, grid, text, image}, props as an object.
- Keep props concise and schema-friendly (no HTML, no markdown).
- If you cannot satisfy the schema, output exactly: {"error":"schema_violation"}.
