import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class JsonlTraceWriter:
    """Append one JSON object per Agent or evaluation event."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, run_id: str, event: str, **fields: Any) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "event": event,
            **fields,
        }
        line = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="\n") as trace_file:
                trace_file.write(line + "\n")
