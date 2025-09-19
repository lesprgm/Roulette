from pathlib import Path
from jsonschema.validators import Draft202012Validator
from jsonschema import ValidationError

# Load the JSON Schema once at import time
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "page_schema.json"
_SCHEMA = None
_VALIDATOR = None

def _load_schema():
    global _SCHEMA, _VALIDATOR
    if _SCHEMA is None:
        import json
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            _SCHEMA = json.load(f)
        Draft202012Validator.check_schema(_SCHEMA)
        _VALIDATOR = Draft202012Validator(_SCHEMA)

# Public function: validate a page instance (raises ValidationError if bad)
def validate_page(instance: dict) -> None:
    _load_schema()
    _VALIDATOR.validate(instance)

# Helper to collect readable errors (for API responses)
def collect_errors(instance: dict) -> list[dict]:
    _load_schema()
    errors = []
    for e in _VALIDATOR.iter_errors(instance):
        errors.append({
            "path": list(e.path),
            "message": e.message,
            "validator": e.validator,
            "validator_value": e.validator_value
        })
    # Sort by JSON path for stable output
    errors.sort(key=lambda x: str(x["path"]))
    return errors
