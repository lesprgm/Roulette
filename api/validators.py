from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


class NdwBackground(BaseModel):
    style: Optional[str] = None
    class_: Optional[str] = Field(default=None, alias="class")


class NdwSnippetV1(BaseModel):
    kind: Literal["ndw_snippet_v1"]
    title: Optional[str] = None
    background: Optional[NdwBackground] = None
    css: Optional[str] = None
    html: Optional[str] = None
    js: Optional[str] = None


class FullPageHtml(BaseModel):
    kind: Literal["full_page_html"]
    html: str


class CustomProps(BaseModel):
    html: str
    height: int


class Component(BaseModel):
    id: str
    type: str
    props: CustomProps


class ComponentsDoc(BaseModel):
    components: List[Component]


PageUnion = Union[NdwSnippetV1, FullPageHtml, ComponentsDoc]


def validate_page_doc(page: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate a generated document against Pydantic first, then optional JSON Schema.
    The light fallback preserves compatibility when schemas/jsonschema are unavailable.
    """
    schema_path = Path("schemas/page_schema.json")
    errors: List[Dict[str, Any]] = []

    pydantic_errors: List[Dict[str, Any]] = []
    try:
        TypeAdapter(PageUnion).validate_python(page)
        return True, []
    except ValidationError as exc:
        pydantic_errors = _pydantic_errors(exc)
    except Exception:
        pass

    if not schema_path.exists():
        return _light_validate(page)

    try:
        import jsonschema
    except Exception:
        return _light_validate(page)

    try:
        schema = json.loads(schema_path.read_text())
        validator = jsonschema.Draft202012Validator(schema)
        schema_errors = [
            {"path": ".".join(str(part) for part in err.path) or "(root)", "message": str(err.message)}
            for err in validator.iter_errors(page)
        ]
        if not schema_errors:
            return True, []
        return False, schema_errors + pydantic_errors
    except Exception as exc:
        errors.append({"path": "(schema)", "message": f"schema load/validate error: {exc}"})
        return False, errors


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


def _light_validate(page: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    if "components" not in page or not isinstance(page["components"], list):
        errors.append({"path": "components", "message": "required: components list"})
        return False, errors
    for idx, component in enumerate(page["components"]):
        if not isinstance(component, dict) or "id" not in component:
            errors.append({"path": f"components[{idx}].id", "message": "required property 'id'"})
    return len(errors) == 0, errors


_validate_with_jsonschema = validate_page_doc
