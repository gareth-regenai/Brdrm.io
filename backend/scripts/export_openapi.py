"""Writes the API contract to openapi.json. CI fails if the file is out of date."""

import json
import sys
from pathlib import Path

from boardroom.gateway.app import app

OUT = Path(__file__).resolve().parents[1] / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if OUT.read_text() == render() else 1)
    OUT.write_text(render())
