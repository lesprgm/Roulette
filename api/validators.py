from __future__ import annotations
from typing import Any, Dict, List

def collect_errors(page: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Return a list of {"path": "...", "message": "..."} error dicts.
    Keep messages human-friendly and include the word 'required'
    when a required property is missing (tests look for that).
    """
    errors: List[Dict[str, str]] = []

    
    comps = page.get("components")
    if not isinstance(comps, list):
        errors.append({
            "path": "components",
            "message": "required property 'components' must be an array"
        })
        return errors  # can't go deeper safely

    for idx, comp in enumerate(comps):
        path_prefix = f"components[{idx}]"

        if not isinstance(comp, dict):
            errors.append({
                "path": path_prefix,
                "message": "component must be an object"
            })
            continue

        if "id" not in comp:
            errors.append({
                "path": f"{path_prefix}.id",
                "message": "required property 'id' is missing"
            })
        else:
            cid = comp.get("id")
            if not isinstance(cid, str) or not cid.strip():
                errors.append({
                    "path": f"{path_prefix}.id",
                    "message": "required property 'id' must be a non-empty string"
                })

        if "type" not in comp:
            errors.append({
                "path": f"{path_prefix}.type",
                "message": "required property 'type' is missing"
            })

        if "props" not in comp:
            errors.append({
                "path": f"{path_prefix}.props",
                "message": "required property 'props' is missing"
            })

    # lightweight layout/palette presence checks (kept minimal for tests)
    if "layout" not in page:
        errors.append({"path": "layout", "message": "required property 'layout' is missing"})
    if "palette" not in page:
        errors.append({"path": "palette", "message": "required property 'palette' is missing"})

    return errors


def validate_page(page: Dict[str, Any]) -> None:
    """
    Raise ValueError if there are any errors; otherwise return None.
    FastAPI layer turns this into 422 with the list from collect_errors().
    """
    errs = collect_errors(page)
    if errs:
        raise ValueError("page failed validation")
