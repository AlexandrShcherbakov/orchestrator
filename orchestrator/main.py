import argparse
import datetime
from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Any

import yaml

from orchestrator.proposals import parse_proposal_yaml, validate_docs_only, validate_allowed_prefixes
from orchestrator.apply import apply_proposal
from orchestrator.git_ops import diff_numstat, head_sha, is_clean, branch_exists, checkout_new_branch, current_branch, add_all, commit
from orchestrator.task_logging import make_task_log_dir
from orchestrator.steps import Step, run_step
from orchestrator.project_config import load_project_config
from orchestrator.runner import run_cmd, CmdError
from orchestrator.tasks_io import append_problem, append_done
from orchestrator.llm import LLM, LLMConfig
from orchestrator.agents.architect import run_architect_bootstrap, create_architect_context


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

def prompt_apply(interactive: bool) -> str:
  if not interactive:
    return "apply"
  while True:
    cmd = input("command (apply/skip/abort): ").strip().lower()
    if cmd in ("apply", "skip", "abort"):
      return cmd

def gather_docs_and_architecture(repo: Path) -> dict[str, str]:
  """Собирает всю документацию и информацию об архитектуре из markdown файлов."""
  docs_content = {}

  # Ищем все markdown файлы в docs/
  docs_dir = repo / "docs"
  if not docs_dir.exists():
    return docs_content

  for md_file in docs_dir.rglob("*.md"):
    try:
      # Используем относительный путь от docs/ как ключ
      rel_path = md_file.relative_to(docs_dir)
      content = md_file.read_text(encoding="utf-8")
      docs_content[str(rel_path)] = content
    except Exception as e:
      print(f"[warning] Could not read {md_file}: {e}")

  return docs_content

def get_user_goal_and_requirements() -> dict[str, str]:
  """Получает от пользователя описание задачи простым текстом."""
  print("\n" + "=" * 60)
  print("ARCHITECT TASK DESCRIPTION")
  print("=" * 60)

  print("\nPlease describe what you want to implement or change:")
  print("(You can write as much detail as you need)")
  print("-" * 40)

  # Собираем многострочный ввод
  lines = []
  print("Enter your task description (press Enter twice to finish):")
  while True:
    line = input("").strip()
    if line == "" and lines:  # Пустая строка после ввода текста - конец
      break
    if line != "":  # Игнорируем пустые строки в начале
      lines.append(line)

  task_description = "\n".join(lines).strip()

  if not task_description:
    print("Task description cannot be empty. Please try again...")
    return get_user_goal_and_requirements()

  return {"task_description": task_description}

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
    log = make_task_log_dir(repo, "BOOTSTRAP")
    log.write_json("bootstrap_meta.json", {"repo": str(repo)})

    # Gather current docs, information about architecture based on all md files
    print("[STEP 1] Gathering current documentation and architecture information...")
    docs_content = gather_docs_and_architecture(repo)

    # Log gathered docs for debugging
    log.write_json("gathered_docs.json", {
      "files": list(docs_content.keys()),
      "total_files": len(docs_content)
    })

    print(f"[OK] Gathered {len(docs_content)} documentation files:")
    for file_path in sorted(docs_content.keys()):
      print(f"  - {file_path}")

    # Init Architect agent with this context
    print("[STEP 2] Initializing Architect agent with documentation context...")

    # Create context object with all gathered documentation
    architect_context = create_architect_context(docs_content, repo)

    # Log the architect context for debugging
    log.write_json("architect_context.json", {
        "total_docs": architect_context.total_docs,
        "repo_path": architect_context.repo_path,
        "doc_files": list(architect_context.docs_content.keys())
    })

    print(f"[OK] Architect context initialized with {architect_context.total_docs} documents")

    # Get prompt from user input about current goal and requirements
    print("[STEP 3] Getting user input about goals and requirements...")
    user_input = get_user_goal_and_requirements()

    # Log user input for debugging and tracking
    log.write_json("user_requirements.json", user_input)

    print(f"[OK] User task description captured ({len(user_input['task_description'])} characters)")
    # TODO: Run Architect to get proposal for updating docs/architecture and backlog. Response of the Architect should contain changes in docs + list of tasks. If the architect has any questions, it should ask user, get answers and re-run until it has no more questions.
    # TODO: Notify user about proposed changes and tasks, ask for confirmation to apply.
    # TODO: If confirmed, make a commit for these changes.
    # TODO: Gather current docs, information about architecture based on all md files also add current backlog.
    # TODO: Init TechLead agent with this context.
    # TODO: TechLeads should generate subtasks for each task if it is necessary. We require small commits (less than 300 changed lines).
    # TODO: TechLead only modifies backlog and architecture md files and makes a commit.

    steps: list[Step] = []

    def _step_architect_bootstrap():
      llm = LLM(LLMConfig(
        model="gpt-4o-mini",        # временно
        max_output_tokens=1200,
      ))
      # Контекст у агента минимальный: facts + постановка внутри агента
      res = run_architect_bootstrap(llm, repo, log)
      return {"status": "proposed", "note": "See architect_bootstrap_raw.yaml in logs."}

    steps.append(Step(
      name="architect_bootstrap",
      actor="architect",
      context_summary=(
        "Input: docs/knowledge/facts.md. "
        "Output: proposal YAML logged to logs/.../architect_bootstrap_raw.yaml. "
        "No repo changes in this step."
      ),
      run=_step_architect_bootstrap,
    ))

    total = len(steps)
    for i, s in enumerate(steps, start=1):
      run_step(s, log, args.interactive, i, total)

    print(f"[ok] bootstrap complete. logs at: {log.root}")

    raw = (log.root / "architect_bootstrap_raw.yaml").read_text(encoding="utf-8")
    proposal = parse_proposal_yaml(raw)
    validate_docs_only(repo, proposal)

    log.write_json("proposal_summary.json", {
      "files": [f.path for f in proposal.files],
      "problems": proposal.problems,
    })
    print("[proposal] files:")
    for f in proposal.files:
      print(" ", f.path)
    if proposal.problems:
      print("[proposal] problems:")
      for q in proposal.problems:
        print(" -", q)

    if proposal.problems:
      for q in proposal.problems:
        append_problem(repo, "BOOTSTRAP", q, blocking=True)
      print("[stop] architect reported problems -> recorded in docs/tasks/problems.yaml")
      return 8

    choice = prompt_apply(args.interactive)
    if choice == "skip":
      print("[ok] skipped applying proposal")
      return 0
    if choice == "abort":
      raise SystemExit(130)

    if not is_clean(repo):
      print("[error] working tree not clean")
      return 4

    bname = "bootstrap/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if branch_exists(repo, bname):
      print("[error] branch exists:", bname)
      return 5
    checkout_new_branch(repo, bname)
    log.write_text("bootstrap_branch.txt", bname)

    written = apply_proposal(repo, proposal)
    log.write_json("applied_files.json", {"written": written})

    cfg = load_project_config(repo)
    failed = []
    for c in cfg.checks:
      try:
        res = run_cmd(repo, c.cmd)
        log.write_text(f"bootstrap_check_{c.name}_stdout.txt", res.stdout)
        log.write_text(f"bootstrap_check_{c.name}_stderr.txt", res.stderr)
      except CmdError as e:
        log.write_text(f"bootstrap_check_{c.name}_stdout.txt", e.result.stdout)
        log.write_text(f"bootstrap_check_{c.name}_stderr.txt", e.result.stderr)
        failed.append(c.name)

    if failed:
      append_problem(repo, "BOOTSTRAP", "Bootstrap checks failed: " + ", ".join(failed), blocking=True)
      print("[stop] checks failed -> recorded in docs/tasks/problems.yaml")
      return 6

    add_all(repo)
    commit(repo, "BOOTSTRAP: update docs")
    print("[ok] bootstrap committed on", current_branch(repo))
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

    facts = (repo / "docs" / "knowledge" / "facts.md").read_text(encoding="utf-8")

    # TODO: Gather task info + facts.
    # TODO: Init X (3 by default) Tester agents with this context. They should ask for more context if needed.
    # TODO: Extend Tester contexts they ask.
    # TODO: Get code for new tests from Testers. Apply to repo.
    # TODO: Init X (3 by default) Developer agents with same context as testers + info about proposed tests. They should propose code changes to implement the task and make tests pass. Apply to repo.
    # TODO: Run code checks. If failed, return to Testers/Developers for another iteration.
    # TODO: Run code tests. If failed, return to Testers/Developers for another iteration.
    # TODO: Init X (3 by default) Architect Reviewer agents with this context. They should ask for more context if needed.
    # TODO: Get feedback from Architect Reviewers. If there are problems return to Testers/Developers for another iteration.
    # TODO: Init X (3 by default) Developer Reviewer agents with this context. They should ask for more context if needed.
    # TODO: Get feedback from Developer Reviewers. If there are problems return to Testers/Developers for another iteration.
    # TODO: Init X (3 by default) Code style Reviewer agents with this context. They should ask for more context if needed.
    # TODO: Get feedback from Code style Reviewers. If there are problems return to Testers/Developers for another iteration.
    # TODO: If all good, commit with message "{task.id}: {task.title}".
    # TODO: Start with the next ready task.

    tester_yaml_holder = {"raw": ""}

    def _tester_step():
      llm = LLM(LLMConfig(model="gpt-4o-mini", max_output_tokens=1200))
      raw = run_tester(llm, repo, task.id, task.title, task.description, facts, log)
      tester_yaml_holder["raw"] = raw
      return {"status": "proposed"}

    steps.append(Step(
      name="tester_generate",
      actor="tester",
      context_summary="Generate test proposal (allowed: tests/, docs/tests/).",
      run=_tester_step
    ))

    def _apply_tests():
      raw = tester_yaml_holder["raw"]
      proposal = parse_proposal_yaml(raw)  # уже умеет strip fences
      validate_allowed_prefixes(repo, proposal, ["tests", "docs/tests"])
      written = apply_proposal(repo, proposal)
      log.write_json("tester_applied.json", {"written": written})
      return {"written": written}

    steps.append(Step(
      name="tester_apply",
      actor="orchestrator",
      context_summary="Apply tester proposal to repo (tests only).",
      run=_apply_tests
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

    def _commit_tests():
      add_all(repo)
      commit(repo, f"{task.id}: add tests")
      return {"committed": True}

    steps.append(Step(
      name="commit_tests",
      actor="orchestrator",
      context_summary="Create one commit with tests changes.",
      run=_commit_tests
    ))

    total = len(steps)
    results = []
    for i, s in enumerate(steps, start=1):
      r = run_step(s, log, args.interactive, i, total)
      results.append((s.name, r))

    failed = []
    for name, r in results:
      if name.startswith("check_") and isinstance(r, dict) and r.get("ok") is False:
        failed.append(name)

    if failed:
      msg = "Checks failed: " + ", ".join(failed)
      append_problem(repo, task.id, msg, blocking=True)
      print(f"[stop] {msg} -> recorded in docs/tasks/problems.yaml")
      return 6

    numstat = diff_numstat(repo)
    log.write_text("diff_numstat.txt", numstat)

    # грубая оценка: суммируем добавленные+удалённые строки
    added = deleted = 0
    for line in numstat.splitlines():
      a, d, _path = line.split("\t", 2)
      if a.isdigit():
        added += int(a)
      if d.isdigit():
        deleted += int(d)

    if added + deleted > 300:
      append_problem(repo, task.id, f"Diff too large: {added}+{deleted} lines", blocking=True)
      print(f"[stop] diff too large ({added}+{deleted}) -> recorded in problems")
      return 7

    append_done(repo, task.id, task.title)

    add_all(repo)
    commit(repo, f"{task.id}: {task.title}")

    print("[ok] committed")
    return 0

if __name__ == "__main__":
  raise SystemExit(main())
