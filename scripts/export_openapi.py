#!/usr/bin/env python3
"""Export OpenAPI specification from FastAPI application.

Usage:
    python scripts/export_openapi.py [--output openapi.json]
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from epip.main import app


def export_openapi(output_path: str = "openapi.json") -> None:
    """Export OpenAPI schema to JSON file."""
    openapi_schema = app.openapi()

    output = Path(output_path)
    output.write_text(json.dumps(openapi_schema, indent=2, ensure_ascii=False))

    print(f"OpenAPI specification exported to: {output.absolute()}")
    print(f"  - Title: {openapi_schema.get('info', {}).get('title')}")
    print(f"  - Version: {openapi_schema.get('info', {}).get('version')}")
    print(f"  - Paths: {len(openapi_schema.get('paths', {}))}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export OpenAPI specification")
    parser.add_argument(
        "--output", "-o",
        default="openapi.json",
        help="Output file path (default: openapi.json)"
    )
    args = parser.parse_args()

    export_openapi(args.output)
