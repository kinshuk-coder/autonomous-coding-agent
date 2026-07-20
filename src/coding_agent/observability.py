from __future__ import annotations
import json, sqlite3
from pathlib import Path
class RunStore:
    def __init__(self, repo: Path) -> None:
        folder = repo / ".agent"; folder.mkdir(exist_ok=True)
        self.db = sqlite3.connect(folder / "runs.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (run_id TEXT, event TEXT, payload TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    def log(self, run_id: str, event: str, payload: object) -> None:
        self.db.execute("INSERT INTO events(run_id,event,payload) VALUES(?,?,?)", (run_id, event, json.dumps(payload, default=str))); self.db.commit()
