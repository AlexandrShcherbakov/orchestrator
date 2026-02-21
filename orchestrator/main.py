import argparse
from pathlib import Path
import sys

def parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(prog="orchestrator")
  p.add_argument(
    "--repo",
    required=True,
    help="Path to target project git repository (the repo where tasks/docs/code live).",
  )
  p.add_argument(
    "--interactive",
    action="store_true",
    help="Stop before each step and ask for confirmation.",
  )
  return p.parse_args()

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
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
