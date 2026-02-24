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

def add_all(repo: Path) -> None:
  _run(repo, ["add", "-A"])

def commit(repo: Path, message: str) -> None:
  _run(repo, ["commit", "-m", message])

def diff_numstat(repo: Path) -> str:
  return _run(repo, ["diff", "--numstat"])

def apply_diff(repo: Path, diff_content: str) -> str | None:
  p = subprocess.run(
    ["git", "apply", "--whitespace=fix"],
    cwd=str(repo),
    input=diff_content,
    text=True,
    capture_output=True,
  )
  if p.returncode != 0:
    return p.stderr or p.stdout
  return None

def apply_diff_for_file(repo: Path, file: str, diff_content: str) -> str | None:
  p = subprocess.run(
    ["git", "apply", "--whitespace=fix", f"--include={file}"],
    cwd=str(repo),
    input=diff_content,
    text=True,
    capture_output=True,
  )
  if p.returncode != 0:
    return p.stderr or p.stdout
  return None

def check_apply_diff_for_file(repo: Path, file: str, diff_content: str) -> str | None:
  p = subprocess.run(
    ["git", "apply", "--check", "--whitespace=fix", f"--include={file}"],
    cwd=str(repo),
    input=diff_content,
    text=True,
    capture_output=True,
  )
  if p.returncode != 0:
    return p.stderr or p.stdout
  return None


