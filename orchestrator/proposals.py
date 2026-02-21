from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ProposedFile:
  path: str
  content: str

@dataclass(frozen=True)
class Proposal:
  files: list[ProposedFile]
  problems: list[str]

def parse_proposal_yaml(text: str) -> Proposal:
  data = yaml.safe_load(text) or {}
  pcs = data.get("proposed_changes", []) or []
  files: list[ProposedFile] = []
  for i, item in enumerate(pcs):
    if not isinstance(item, dict):
      raise ValueError(f"proposed_changes[{i}] must be a dict")
    path = str(item.get("path", "")).strip()
    content = str(item.get("content", ""))
    if not path:
      raise ValueError(f"proposed_changes[{i}] missing path")
    files.append(ProposedFile(path=path, content=content))
  probs = [str(x).strip() for x in (data.get("problems", []) or []) if str(x).strip()]
  return Proposal(files=files, problems=probs)

def validate_docs_only(repo: Path, proposal: Proposal) -> None:
  for f in proposal.files:
    p = (repo / f.path).resolve()
    if not str(p).startswith(str((repo / "docs").resolve())):
      raise ValueError(f"Proposed path outside docs/: {f.path}")
