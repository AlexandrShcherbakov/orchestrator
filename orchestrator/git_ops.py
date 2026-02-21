from __future__ import annotations
import subprocess
from pathlib import Path

class GitError(RuntimeError):
  pass

def _run(repo: Path, args: list[str]) -> str:
  p = subprocess.run(
    ["git", *args],
    cwd=str(repo),
    capture_output=True,
    text=True,
  )
  if p.returncode != 0:
    raise GitError((p.stderr or p.stdout or "").strip() or f"git {' '.join(args)} failed")
  return (p.stdout or "").strip()

def head_sha(repo: Path) -> str:
  return _run(repo, ["rev-parse", "HEAD"])

def is_clean(repo: Path) -> bool:
  out = _run(repo, ["status", "--porcelain"])
  return out.strip() == ""

def current_branch(repo: Path) -> str:
  return _run(repo, ["rev-parse", "--abbrev-ref", "HEAD"])

def branch_exists(repo: Path, name: str) -> bool:
  try:
    _run(repo, ["rev-parse", "--verify", name])
    return True
  except GitError:
    return False

def checkout_new_branch(repo: Path, name: str) -> None:
  _run(repo, ["checkout", "-b", name])
