from __future__ import annotations
from pathlib import Path

from orchestrator.proposals import Proposal


def apply_proposal(repo: Path, proposal: Proposal) -> list[str]:
  written: list[str] = []
  for f in proposal.files:
    p = repo / f.path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f.content, encoding="utf-8")
    written.append(f.path)
  return written
