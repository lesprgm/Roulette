from __future__ import annotations

from typing import Any, Dict, List, Literal, Tuple

from pydantic import BaseModel, ValidationError


class FullPageHtml(BaseModel):
    kind: Literal["full_page_html"]
    html: str


def validate_page_doc(page: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Validate the single generated-document shape used by production."""
    try:
        FullPageHtml.model_validate(page)
        return True, []
    except ValidationError as exc:
        return False, _pydantic_errors(exc)


def _pydantic_errors(exc: ValidationError) -> List[Dict[str, Any]]:
    try:
        return [
            {
                "path": ".".join(str(part) for part in err.get("loc", [])) or "(root)",
                "message": err.get("msg", "invalid"),
            }
            for err in exc.errors()
        ]
    except Exception:
        return [{"path": "(root)", "message": "invalid"}]
