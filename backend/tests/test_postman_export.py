"""Tests for the OpenAPI-derived Postman collection exporter."""

import json
from pathlib import Path

from app.main import app
from scripts.export_postman import (
    DEFAULT_BASE_URL,
    POSTMAN_SCHEMA,
    build_collection,
    export_collection,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "backend" / "examples"


def _walk_items(items):
    for item in items:
        if "request" in item:
            yield item
        else:
            yield from _walk_items(item.get("item", []))


def test_postman_collection_covers_every_openapi_operation_and_examples():
    collection = build_collection()
    requests = list(_walk_items(collection["item"]))

    expected_operations = {
        (method.upper(), path)
        for path, path_item in app.openapi()["paths"].items()
        for method in path_item
        if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}
    }
    actual_operations = {
        (
            item["request"]["method"],
            item["request"]["url"].replace("{{baseUrl}}", "").replace(
                ":incident_id", "{incident_id}"
            ).replace(":resource_id", "{resource_id}")
             .replace(":recommendation_id", "{recommendation_id}")
             .replace(":plan_id", "{plan_id}")
             .replace(":alert_id", "{alert_id}")
             .replace(":assessment_id", "{assessment_id}")
             .replace(":action_id", "{action_id}")
             .split("?", 1)[0],
        )
        for item in requests
    }

    assert collection["info"]["schema"] == POSTMAN_SCHEMA
    assert collection["variable"][0] == {
        "key": "baseUrl",
        "value": DEFAULT_BASE_URL,
        "type": "string",
    }
    assert expected_operations.issubset(actual_operations)

    included_examples = {
        item["name"].rsplit(" - ", 1)[-1]
        for item in requests
        if " - " in item["name"]
    }
    expected_examples = {path.name for path in EXAMPLES.glob("*.json")}
    assert included_examples == expected_examples

    for item in requests:
        request = item["request"]
        if "body" in request:
            assert request["body"]["mode"] == "raw"
            assert request["body"]["options"]["raw"]["language"] == "json"
            json.loads(request["body"]["raw"])


def test_export_collection_writes_valid_json_with_override(tmp_path):
    output = export_collection(tmp_path / "collection.json", base_url="http://localhost:9999/")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["variable"][0]["value"] == "http://localhost:9999"
    assert payload["info"]["name"] == "ResQ Command API"
