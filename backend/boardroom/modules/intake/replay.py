"""Replays recorded skill 1 answers, matched on the file's columns. Used by the tests
(FR-13.2) and by local demos without an API key. Never allowed in staging or production."""

import json
from pathlib import Path
from typing import Any


class ReplayClient:
    model = "recorded"

    def __init__(self, directory: str | Path) -> None:
        self.responses: dict[tuple[str, ...], Any] = {}
        for path in Path(directory).glob("*.json"):
            data = json.loads(path.read_text())
            self.responses[tuple(data["columns"])] = data["response"]
        self.payloads: list[dict[str, Any]] = []
        self.override: Any = None

    def interpret(self, payload: dict[str, Any]) -> Any:
        from boardroom.modules.intake.skill1 import SkillUnavailable

        self.payloads.append(payload)
        if self.override is not None:
            return self.override
        body = payload["user"].split("<file>\n", 1)[1].rsplit("\n</file>", 1)[0]
        columns = tuple(c["name"] for c in json.loads(body)["columns"])
        if columns not in self.responses:
            raise SkillUnavailable("no recorded answer for these columns")
        return self.responses[columns]
