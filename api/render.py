from __future__ import annotations
from typing import Dict, Any, List
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Jinja environment that looks in ./templates
_env = Environment(
    loader=FileSystemLoader(os.path.join(os.getcwd(), "templates")),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)

def _render_component(comp: Dict[str, Any]) -> str:
    """
    Map a component {id,type,props} to a partial template.
    If we don't have a matching partial, fall back to a generic box.
    """
    ctype = (comp.get("type") or "").lower()
    tpl_name = f"partials/{ctype}.html"
    try:
        tpl = _env.get_template(tpl_name)
    except Exception:
        tpl = _env.get_template("partials/generic.html")
    return tpl.render(comp=comp, props=comp.get("props", {}))

def render_page_html(page: Dict[str, Any]) -> str:
    """
    Given a validated page JSON (your schema), build the full HTML string.
    """
    components: List[Dict[str, Any]] = page.get("components", [])
    rendered = [_render_component(c) for c in components]

    base = _env.get_template("page.html")
    return base.render(
        page=page,
        rendered_components=rendered,
        layout=page.get("layout", {"flow": "stack"}),
        palette=page.get("palette", {"primary": "slate", "accent": "indigo"}),
        links=page.get("links", []),
    )
