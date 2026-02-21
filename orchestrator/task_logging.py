from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json

@dataclass(frozen=True)
class TaskLog:
  root: Path  # .../project/logs/task_T-001/

  def write_text(self, name: str, text: str) -> None:
    p = self.root / name
    p.write_text(text, encoding="utf-8")

  def write_json(self, name: str, obj) -> None:
    p = self.root / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def make_task_log_dir(project_repo: Path, task_id: str) -> TaskLog:
  logs_root = project_repo / "logs"
  ts = datetime.now().strftime("%Y%m%d_%H%M%S")
  task_root = logs_root / f"task_{task_id}" / ts
  task_root.mkdir(parents=True, exist_ok=True)
  return TaskLog(root=task_root)
