import os
import os
from pathlib import Path
from .runner import run_cmd, CmdError

EXCLUDED_DIRS = ['.git', '.venv', 'logs', '__pycache__', '*.pyc', '*.egg-info']

def _is_within_cwd(path: str) -> bool:
  try:
    abs_path = os.path.realpath(path)
    abs_cwd = os.path.realpath(os.getcwd())
    return abs_path.startswith(abs_cwd + os.sep) or abs_path == abs_cwd
  except (ValueError, OSError):
    return False

def ls(path: str) -> str:
  # if path is a file, return path
  if os.path.isfile(path):
    return path
  if not os.path.isdir(path):
    return "<FORBIDDEN>"

  if not _is_within_cwd(path):
    return "<FORBIDDEN>"

  try:
    res = run_cmd(Path(os.getcwd()), ["ls", "-A", "-p", "-1", path])
    lines = [l for l in res.stdout.splitlines()]
  except CmdError as e:
    # no access or other ls error
    return ""

  items = []
  for item in lines:
    item_clean = item.rstrip('/')
    item_path = os.path.join(path, item_clean)
    if any(excluded in item_path for excluded in EXCLUDED_DIRS):
      continue
    items.append(item)
  return "\n".join(items)

def cat(path: str) -> str:
  if not os.path.isfile(path):
    return "<FORBIDDEN>"
  if not _is_within_cwd(path):
    return "<FORBIDDEN>"
  try:
    res = run_cmd(Path(os.getcwd()), ["cat", path])
    return res.stdout
  except CmdError:
    return ""

def tree(path: str, depth: int) -> str:
  if depth < 0:
    return ""
  if not os.path.isdir(path):
    return "<FORBIDDEN>"
  if not _is_within_cwd(path):
    return "<FORBIDDEN>"

  # use find to enumerate entries, then build a similar tree output
  try:
    res = run_cmd(Path(os.getcwd()), ["find", path, "-print"])
    paths = [p for p in res.stdout.splitlines()]
  except CmdError:
    return ""

  # normalize and sort
  root = Path(path)
  entries = [Path(p) for p in paths]
  entries.sort()

  result_lines = []
  # build directory-wise
  dirs_seen = set()
  for p in entries:
    try:
      rel = p.relative_to(root)
    except Exception:
      continue
    # skip the root itself (will be handled below)
    # filter directories by exact name and files by substring match as before
    if p.is_dir():
      name = p.name
      if name in EXCLUDED_DIRS:
        continue
    else:
      if any(excluded in p.name for excluded in EXCLUDED_DIRS):
        continue

    # determine parent dir to print its header if not already
    parent = p if p.is_dir() else p.parent
    if parent not in dirs_seen:
      # compute level for parent
      if parent == root:
        parent_level = 0
      else:
        try:
          rel_parent = parent.relative_to(root)
          parent_level = len(rel_parent.parts)
        except Exception:
          parent_level = 0
      if parent == root:
        basename = os.path.basename(str(root))
      else:
        basename = parent.name
      indent = " " * 4 * parent_level
      result_lines.append(f"{indent}{basename}/")
      dirs_seen.add(parent)

    if p.is_dir():
      continue
    # file entry
    if p.parent == root:
      file_level = 0
    else:
      try:
        rel_parent = p.parent.relative_to(root)
        file_level = len(rel_parent.parts)
      except Exception:
        file_level = 0
    indent = " " * 4 * file_level
    result_lines.append(f"{indent}    {p.name}")

  # Now filter out entries deeper than depth
  filtered = []
  for line in result_lines:
    # count leading spaces to determine level
    spaces = len(line) - len(line.lstrip(' '))
    level = spaces // 4
    if level > depth:
      continue
    filtered.append(line)

  return "\n".join(filtered)

def grep(path: str, pattern: str) -> str:
  if not path:
    return "<FORBIDDEN>"
  if not _is_within_cwd(path):
    return "<FORBIDDEN>"

  # prepare exclude args
  exclude_args = []
  for ex in EXCLUDED_DIRS:
    if '*' in ex or '?' in ex:
      exclude_args += ["--exclude", ex]
    else:
      exclude_args += ["--exclude-dir", ex]

  try:
    if os.path.isfile(path):
      cmd = ["grep", "-n", "-I", "--"] + [pattern, path]
    elif os.path.isdir(path):
      cmd = ["grep", "-R", "-n", "-I"] + exclude_args + ["--"] + [pattern, path]
    else:
      return "<FORBIDDEN>"
    res = run_cmd(Path(os.getcwd()), cmd)
    return res.stdout
  except CmdError as e:
    # grep exit code 1 == no matches
    if hasattr(e, "result") and e.result.returncode == 1:
      return ""
    return ""