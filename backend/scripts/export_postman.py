#!/usr/bin/env python3
"""Export the current FastAPI OpenAPI document as a Postman v2.1 collection.

Run from the repository root:
    python backend/scripts/export_postman.py
    python backend/scripts/export_postman.py --output /tmp/resq.postman.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
EXAMPLES_DIR = BACKEND_DIR / "examples"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


POSTMAN_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _resolve_schema_ref(schema: dict[str, Any], openapi: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    prefix = "#/components/schemas/"
    if ref.startswith(prefix):
        return openapi.get("components", {}).get("schemas", {}).get(ref[len(prefix):], {})
    return schema


def _request_body_example(operation: dict[str, Any], openapi: dict[str, Any]) -> Any:
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    media = content.get("application/json") or next(iter(content.values()), {})
    examples = media.get("examples") or {}
    if examples:
        first = next(iter(examples.values()))
        if isinstance(first, dict) and "value" in first:
            return first["value"]
    if "example" in media:
        return media["example"]
    schema = _resolve_schema_ref(media.get("schema") or {}, openapi)
    if "example" in schema:
        return schema["example"]
    schema_examples = schema.get("examples")
    if isinstance(schema_examples, list) and schema_examples:
        return schema_examples[0]
    return {}


def _example_files(path: str, method: str) -> list[Path]:
    if method == "post" and path == "/api/incidents":
        return sorted(EXAMPLES_DIR.glob("incident_*.json"))
    if method == "post" and path == "/api/resources":
        return sorted(EXAMPLES_DIR.glob("resource_*.json"))
    if method == "post" and path.endswith("/decision"):
        return sorted(EXAMPLES_DIR.glob("decision_*.json"))
    return []


def _postman_path(path: str) -> str:
    return re.sub(r"\{([^{}]+)\}", r":\1", path)


def _request_url(path: str, operation: dict[str, Any]) -> str:
    raw = "{{baseUrl}}" + _postman_path(path)
    query_parameters = [
        parameter
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "query"
    ]
    if query_parameters:
        pairs = []
        for parameter in query_parameters:
            name = parameter["name"]
            schema = parameter.get("schema") or {}
            default = schema.get("default", "")
            example = parameter.get("example", default)
            value = str(example) if example != "" else "{{" + name + "}}"
            pairs.append(f"{name}={value}")
        raw += "?" + "&".join(pairs)
    return raw


def _request_item(
    path: str,
    method: str,
    operation: dict[str, Any],
    openapi: dict[str, Any],
    *,
    body: Any | None = None,
    example_name: str | None = None,
) -> dict[str, Any]:
    summary = operation.get("summary") or f"{method.upper()} {path}"
    name = summary if example_name is None else f"{summary} - {example_name}"
    request: dict[str, Any] = {
        "method": method.upper(),
        "header": [{"key": "Accept", "value": "application/json"}],
        "url": _request_url(path, operation),
        "description": operation.get("description") or summary,
    }
    if "requestBody" in operation:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        example_body = _request_body_example(operation, openapi) if body is None else body
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(example_body, indent=2, ensure_ascii=False),
            "options": {"raw": {"language": "json"}},
        }
    if example_name:
        request["description"] += f"\n\nExample request body loaded from backend/examples/{example_name}."
    return {"name": name, "request": request}


def build_collection(
    openapi: dict[str, Any] | None = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """Build a Postman v2.1 collection from app.openapi() and checked-in examples."""
    document = openapi if openapi is not None else app.openapi()
    folders: dict[str, list[dict[str, Any]]] = {}

    for path, path_item in sorted(document.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            folder_name = (operation.get("tags") or ["Other"])[0]
            folder = folders.setdefault(folder_name, [])
            example_files = _example_files(path, method.lower())

            if example_files:
                for example_file in example_files:
                    body = json.loads(example_file.read_text(encoding="utf-8"))
                    folder.append(
                        _request_item(
                            path,
                            method,
                            operation,
                            document,
                            body=body,
                            example_name=example_file.name,
                        )
                    )
            else:
                folder.append(_request_item(path, method, operation, document))

    collection_items = [
        {"name": folder, "item": folders[folder]}
        for folder in sorted(folders)
    ]
    return {
        "info": {
            "name": "ResQ Command API",
            "description": (
                "Generated from the FastAPI OpenAPI schema. Academic prototype only: "
                "AUTO dispatch and response operations are simulated; this collection "
                "does not contact real emergency services."
            ),
            "version": "1.0.0",
            "schema": POSTMAN_SCHEMA,
        },
        "item": collection_items,
        "variable": [
            {
                "key": "baseUrl",
                "value": base_url.rstrip("/"),
                "type": "string",
            }
        ],
    }


def export_collection(output: Path, *, base_url: str = DEFAULT_BASE_URL) -> Path:
    collection = build_collection(base_url=base_url)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(collection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "postman_collection.json",
        help="Output JSON file (default: docs/postman_collection.json).",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Initial Postman baseUrl variable (default: {DEFAULT_BASE_URL}).",
    )
    args = parser.parse_args()
    output = export_collection(args.output, base_url=args.base_url)
    total = sum(len(folder["item"]) for folder in build_collection()["item"])
    print(f"Exported {total} requests to {output}")
    print(f"Postman baseUrl default: {args.base_url.rstrip('/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
