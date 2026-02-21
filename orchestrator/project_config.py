from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import yaml

@dataclass(frozen=True)
class CheckCmd:
  name: str
  cmd: list[str]

@dataclass(frozen=True)
class ProjectConfig:
  checks: list[CheckCmd]

def load_project_config(repo: Path) -> ProjectConfig:
  p = repo / "docs" / "orchestrator.yaml"
  if not p.exists():
    raise FileNotFoundError(f"Missing project config: {p}")
  data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
  checks_raw = data.get("checks", []) or []
  checks: list[CheckCmd] = []
  for i, item in enumerate(checks_raw):
    if not isinstance(item, dict):
      raise ValueError(f"checks[{i}] must be a dict")
    name = str(item.get("name", "")).strip()
    cmd = list(item.get("cmd", []) or [])
    if not name or not cmd:
      raise ValueError(f"checks[{i}] must have name and cmd")
    checks.append(CheckCmd(name=name, cmd=[str(x) for x in cmd]))
  return ProjectConfig(checks=checks)
