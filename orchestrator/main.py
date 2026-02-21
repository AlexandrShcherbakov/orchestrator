import argparse
from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Any

import yaml

from orchestrator.git_ops import head_sha, is_clean, branch_exists, checkout_new_branch, current_branch
from orchestrator.logging import make_task_log_dir
from orchestrator.steps import Step, run_step
from orchestrator.project_config import load_project_config
from orchestrator.runner import run_cmd, CmdError


def parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(prog="orchestrator")
  p.add_argument("--repo", required=True)
  p.add_argument("--interactive", action="store_true")

  sub = p.add_subparsers(dest="cmd", required=True)

  sub.add_parser("bootstrap", help="Run architect/techlead to update docs and backlog.")
  sub.add_parser("run", help="Pick next task from backlog and execute pipeline.")

  return p.parse_args()

@dataclass(frozen=True)
class Task:
  id: str
  title: str
  description: str
  deps: list[str]
  status: str
  type: str

def load_tasks(backlog_path: Path) -> list[Task]:
  data: list[dict[str, Any]] = yaml.safe_load(backlog_path.read_text(encoding="utf-8")) or []
  tasks: list[Task] = []
  for i, item in enumerate(data):
    if not isinstance(item, dict):
      raise ValueError(f"Backlog item #{i} is not a dict")
    tasks.append(Task(
      id=str(item.get("id", "")).strip(),
      title=str(item.get("title", "")).strip(),
      description=str(item.get("description", "")).strip(),
      deps=list(item.get("deps", []) or []),
      status=str(item.get("status", "")).strip(),
      type=str(item.get("type", "")).strip(),
    ))
  return tasks

def load_done_ids(done_path: Path) -> set[str]:
  data: list[dict[str, Any] | str] = yaml.safe_load(done_path.read_text(encoding="utf-8")) or []
  ids: set[str] = set()
  for item in data:
    if isinstance(item, dict) and "id" in item:
      ids.add(str(item["id"]).strip())
    elif isinstance(item, str):
      ids.add(item.strip())
  return ids

def pick_next_ready(tasks: list[Task], done_ids: set[str]) -> Task | None:
  for t in tasks:
    if t.status != "ready":
      continue
    if all(dep in done_ids for dep in t.deps):
      return t
  return None

def prompt_next(interactive: bool, step_name: str) -> None:
  if not interactive:
    return
  print(f"[interactive] next step: {step_name}")
  while True:
    cmd = input("command (next/abort): ").strip().lower()
    if cmd == "next":
      return
    if cmd == "abort":
      raise SystemExit(130)

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

  print(f"[ok] repo: {repo}")
  print(f"[ok] interactive: {args.interactive}")

  check_project_contract(repo)
  print("[ok] project contract valid")

  if args.cmd == "bootstrap":
    print("[ok] bootstrap (stub): architect/techlead would run here")
    print("[hint] update docs/knowledge/facts.md and docs/tasks/backlog.yaml")
    return 0
  elif args.cmd == "run":
    backlog = repo / "docs" / "tasks" / "backlog.yaml"
    done = repo / "docs" / "tasks" / "done.yaml"

    tasks = load_tasks(backlog)
    done_ids = load_done_ids(done)
    task = pick_next_ready(tasks, done_ids)

    if task is None:
      print("[ok] no ready tasks")
      return 0

    log = make_task_log_dir(repo, task.id)
    log.write_json("task.json", {
        "id": task.id,
        "title": task.title,
        "deps": task.deps,
        "type": task.type,
    })

    steps: list[Step] = []

    steps.append(Step(
      name="git_precheck",
      actor="orchestrator",
      context_summary="Ensure working tree clean; record HEAD and current branch.",
      run=lambda: {
        "head": head_sha(repo),
        "branch": current_branch(repo),
        "clean": is_clean(repo),
      }
    ))

    def _create_branch():
      if not is_clean(repo):
        raise SystemExit(4)
      branch_name = f"task/{task.id}"
      if branch_exists(repo, branch_name):
        raise SystemExit(5)
      checkout_new_branch(repo, branch_name)
      return {"now_on": current_branch(repo), "branch": branch_name}

    steps.append(Step(
      name="git_create_branch",
      actor="orchestrator",
      context_summary=f"Create and checkout branch task/{task.id}.",
      run=_create_branch
    ))

    cfg = load_project_config(repo)
    log.write_json("project_config.json", {"checks": [{"name": c.name, "cmd": c.cmd} for c in cfg.checks]})

    def make_check_step(check_name: str, cmd: list[str]) -> Step:
      def _run():
        try:
          res = run_cmd(repo, cmd)
          log.write_text(f"check_{check_name}_stdout.txt", res.stdout)
          log.write_text(f"check_{check_name}_stderr.txt", res.stderr)
          return {"ok": True, "rc": res.returncode}
        except CmdError as e:
          log.write_text(f"check_{check_name}_stdout.txt", e.result.stdout)
          log.write_text(f"check_{check_name}_stderr.txt", e.result.stderr)
          return {"ok": False, "rc": e.result.returncode}
      return Step(
        name=f"check_{check_name}",
        actor="orchestrator",
        context_summary="Run command: " + " ".join(cmd),
        run=_run,
      )

    for c in cfg.checks:
      steps.append(make_check_step(c.name, c.cmd))

    total = len(steps)
    for i, s in enumerate(steps, start=1):
      run_step(s, log, args.interactive, i, total)

    return 0

if __name__ == "__main__":
  raise SystemExit(main())
