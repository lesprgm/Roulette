import json
from jsonschema.validators import Draft202012Validator

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_gold_validates_against_schema():
    schema = load_json("schemas/page_schema.json")
    instance = load_json("example_outputs/gold.json")

    # 1) Ensure the schema itself is valid JSON Schema
    Draft202012Validator.check_schema(schema)

    # 2) Validate the instance against the schema
    validator = Draft202012Validator(schema)
    validator.validate(instance)
