import argparse
import os
from pathlib import Path
import sys


from orchestrator.task_logging import make_task_log_dir
from orchestrator.execution_context import Context
from orchestrator.agents.developer import Developer
from orchestrator.agents.reviewer import Reviewer
from orchestrator.git_ops import add_all, commit


def parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(prog="orchestrator")
  p.add_argument("--repo", required=True)

  return p.parse_args()

def check_project_contract(repo: Path) -> None:
  required = [
    repo / "docs" / "knowledge" / "facts.md",
    repo / "docs" / "tasks" / "backlog.yaml",
    repo / "docs" / "tasks" / "done.yaml",
    repo / "docs" / "tasks" / "problems.yaml",
  ]

  missing = [p for p in required if not p.exists()]
  if missing:
    print("[error] project does not satisfy orchestrator contract:", file=sys.stderr)
    for p in missing:
      print(f"  missing: {p.relative_to(repo)}", file=sys.stderr)
    raise SystemExit(3)


def main() -> int:
  args = parse_args()
  repo = Path(args.repo).expanduser().resolve()

  if not repo.exists():
    print(f"[error] repo path does not exist: {repo}", file=sys.stderr)
    return 2

  git_dir = repo / ".git"
  if not git_dir.exists():
    print(f"[error] not a git repo (no .git): {repo}", file=sys.stderr)
    return 2

  os.chdir(repo)

  print(f"[ok] repo: {repo}")

  check_project_contract(repo)
  print("[ok] project contract valid")

  log = make_task_log_dir(repo, "DEV")
  context = Context(log)
  dev = Developer()
  print("What task should I do?")
  context.prompt_context = {
    "TASK": input(),
  }
  dev.execute_task(repo, context)
  rev = Reviewer()
  rev.review_task(repo, context)
  while not context.review_finished:
    dev.execute_task(repo, context)
    rev.review_task(repo, context)

  for change in context.new_content:
    path = repo / change["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(change["patch"])

  add_all(repo)
  commit(repo, context.commit_message)

  return 0

if __name__ == "__main__":
  raise SystemExit(main())
