from __future__ import annotations
from pathlib import Path

import yaml


def _read_yaml_list(p: Path):
  if not p.exists():
    return []
  data = yaml.safe_load(p.read_text(encoding="utf-8"))
  return data or []


def _write_yaml(p: Path, data) -> None:
  p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def append_done(repo: Path, task_id: str, title: str) -> None:
  p = repo / "docs" / "tasks" / "done.yaml"
  data = _read_yaml_list(p)
  data.append({"id": task_id, "title": title})
  _write_yaml(p, data)


def append_problem(repo: Path, task_id: str, question: str, blocking: bool = True) -> None:
  p = repo / "docs" / "tasks" / "problems.yaml"
  data = _read_yaml_list(p)
  data.append({"task": task_id, "question": question, "blocking": blocking})
  _write_yaml(p, data)
