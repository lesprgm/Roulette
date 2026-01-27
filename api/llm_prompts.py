from __future__ import annotations

import json
from typing import Any, Dict, List


def _build_review_prompt(
    doc: Dict[str, Any],
    brief: str,
    category_note: str,
    allow_null_doc: bool = True,
    doc_required: bool = True,
) -> str:
    try:
        serialized = json.dumps(doc, ensure_ascii=False, indent=2)
    except Exception:
        serialized = str(doc)
    if doc_required:
        if allow_null_doc:
            doc_rule = (
                "Always include doc; set doc to null if you made no corrections. "
                "If you corrected the payload, include the corrected doc object."
            )
        else:
            doc_rule = (
                "Always include a doc object (use corrected payload if changed, otherwise the original payload)."
            )
    else:
        doc_rule = (
            "Only include doc if you corrected the payload; otherwise omit doc entirely."
        )
    if doc_required:
        schema_line = (
            '{"ok": true|false, "issues":[{"severity":"info|warn|block","field":"...","message":"..."}],'
            '"notes":"optional summary","doc":{...optional corrected payload...} or null}\n'
            if allow_null_doc
            else '{"ok": true|false, "issues":[{"severity":"info|warn|block","field":"...","message":"..."}],'
            '"notes":"optional summary","doc":{...optional corrected payload...}}\n'
        )
    else:
        schema_line = (
            '{"ok": true|false, "issues":[{"severity":"info|warn|block","field":"...","message":"..."}],'
            '"notes":"optional summary", "doc":{...optional corrected payload...} (omit doc if unchanged)}\n'
        )
    required_line = (
        "Always include keys ok, issues, notes, and doc. "
        if doc_required
        else "Always include ok, issues, and notes. "
    )
    instructions = (
        "You are a compliance reviewer and fixer for interactive web apps. "
        "Inspect the provided JSON payload for safety, policy violations, markup/runtime bugs, or accessibility issues. "
        "If problems are minor, repair them directly and return the corrected payload. "
        "If the experience is unsafe or too broken to repair confidently, reject it. "
        "Hard rules: remove any external <script src>, <link href>, or CSS @import urls (http/https). "
        "Do not rely on external fonts/images/CDNs; assume GSAP, Tailwind CSS, and Lucide are already present globally. "
        "Output JSON only. No explanations. "
        "Respond with compact JSON using this schema:\n"
        f"{schema_line}"
        f"{required_line}If there are no issues, use an empty issues array. "
        "Notes must be <= 160 characters and MUST be an empty string when there are no issues. "
        f"{doc_rule} Only set ok=true if the final payload (original or corrected) is safe, "
        "functional, and accessible."
    )
    return (
        f"{instructions}\n\n"
        f"Brief: {brief or '(auto generated)'}\n"
        f"Category Instruction: {category_note}\n\n"
        "App JSON:\n"
        f"{serialized}\n"
    )


def _review_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string"},
                        "field": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["severity", "field", "message"],
                    "additionalProperties": False,
                },
            },
            "notes": {"type": "string", "maxLength": 160},
            "doc": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "html": {"type": "string"},
                        },
                        "required": ["kind", "html"],
                        "additionalProperties": False,
                    },
                    {"type": "null"},
                ],
            },
        },
        "required": ["ok", "issues", "notes", "doc"],
        "additionalProperties": False,
    }


def _gemini_review_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string"},
                        "field": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["severity", "field", "message"],
                },
            },
            "notes": {"type": "string"},
            "doc": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "html": {"type": "string"},
                },
                "required": ["kind", "html"],
            },
        },
        "required": ["ok"],
    }


def _build_batch_review_prompt(
    documents: List[Dict[str, Any]],
    allow_null_doc: bool = True,
    doc_required: bool = True,
) -> str:
    prompt_sections = []
    for idx, doc in enumerate(documents):
        try:
            serialized = json.dumps(doc, ensure_ascii=False, indent=2)
        except Exception:
            serialized = str(doc)
        prompt_sections.append(f"APP_INDEX: {idx}\nJSON:\n{serialized}\n")
    if doc_required:
        if allow_null_doc:
            doc_rule = (
                "Always include doc; set doc to null if you made no corrections. "
                "If you corrected the payload, include the corrected doc object. "
                "If a document is irreparable, set ok=false and set doc to null."
            )
        else:
            doc_rule = (
                "Always include a doc object (use corrected payload if changed, otherwise the original payload). "
                "If a document is irreparable, set ok=false but still include the original doc."
            )
    else:
        doc_rule = (
            "Only include doc if you corrected the payload; otherwise omit doc entirely. "
            "If a document is irreparable, set ok=false and omit doc."
        )
    if doc_required:
        schema_line = (
            '{"index": <matching APP_INDEX>, "ok": true|false, '
            '"issues":[{"severity":"info|warn|block","field":"...","message":"..."}], '
            '"notes":"optional summary", "doc":{...optional corrected payload...} or null}\n'
            if allow_null_doc
            else '{"index": <matching APP_INDEX>, "ok": true|false, '
            '"issues":[{"severity":"info|warn|block","field":"...","message":"..."}], '
            '"notes":"optional summary", "doc":{...optional corrected payload...}}\n'
        )
    else:
        schema_line = (
            '{"index": <matching APP_INDEX>, "ok": true|false, '
            '"issues":[{"severity":"info|warn|block","field":"...","message":"..."}], '
            '"notes":"optional summary", "doc":{...optional corrected payload...} (omit doc if unchanged)}\n'
        )
    required_line = (
        "Always include ok, issues, notes, and doc in every result. "
        if doc_required
        else "Always include ok, issues, and notes in every result. "
    )
    instructions = (
        "You are a compliance reviewer and fixer for interactive web apps. "
        "Evaluate each document below. Return a JSON object with a 'results' array. "
        "Each array element is:\n"
        f"{schema_line}"
        "Output JSON only. No explanations. The first non-whitespace character MUST be '{'. "
        "Only set ok=true if the payload (original or corrected) is safe, functional, and accessible. "
        "Hard rules: remove any external <script src>, <link href>, or CSS @import urls (http/https). "
        "Do not rely on external fonts/images/CDNs; assume GSAP, Tailwind CSS, and Lucide are already present globally. "
        f"{required_line}If there are no issues, use an empty issues array. "
        "Notes must be <= 160 characters and MUST be an empty string when there are no issues. "
        f"{doc_rule}"
    )
    return instructions + "\n\n---\n" + "\n---\n".join(prompt_sections)


def _batch_review_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "ok": {"type": "boolean"},
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "severity": {"type": "string"},
                                    "field": {"type": "string"},
                                    "message": {"type": "string"},
                                },
                                "required": ["severity", "field", "message"],
                                "additionalProperties": False,
                            },
                        },
                        "notes": {"type": "string", "maxLength": 160},
                        "doc": {
                            "anyOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "kind": {"type": "string"},
                                        "html": {"type": "string"},
                                    },
                                    "required": ["kind", "html"],
                                    "additionalProperties": False,
                                },
                                {"type": "null"},
                            ],
                        },
                    },
                    "required": ["index", "ok", "issues", "notes", "doc"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["results"],
        "additionalProperties": False,
    }


def _gemini_batch_review_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "ok": {"type": "boolean"},
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "severity": {"type": "string"},
                                    "field": {"type": "string"},
                                    "message": {"type": "string"},
                                },
                                "required": ["severity", "field", "message"],
                            },
                        },
                        "notes": {"type": "string"},
                        "doc": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string"},
                                "html": {"type": "string"},
                            },
                            "required": ["kind", "html"],
                        },
                    },
                    "required": ["index", "ok"],
                },
            },
        },
        "required": ["results"],
    }
