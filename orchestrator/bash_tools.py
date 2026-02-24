import os

EXCLUDED_DIRS = ['.git', '.venv', 'logs', '__pycache__', '*.pyc', '*.egg-info']

def ls(path: str) -> str:
  # if path is not a subdirectory of the current directory, return <FORBIDDEN>
  if os.path.isfile(path):
    return path
  if not os.path.isdir(path):
    return "<FORBIDDEN>"

  try:
    # Convert both paths to real paths to handle symlinks, relative paths and drive issues
    abs_path = os.path.realpath(path)
    abs_cwd = os.path.realpath(os.getcwd())

    # Check if the path is within the current directory
    if not abs_path.startswith(abs_cwd + os.sep) and abs_path != abs_cwd:
      return "<FORBIDDEN>"
  except (ValueError, OSError):
    # Handle cases where paths are on different drives or other path issues
    return "<FORBIDDEN>"

  items = []
  for item in os.listdir(path):
    item_path = os.path.join(path, item)
    if any(excluded in item_path for excluded in EXCLUDED_DIRS):
      continue
    if os.path.isdir(item_path):
      items.append(f"{item}/")
    elif os.path.isfile(item_path):
      items.append(f"{item}")
    else:
      items.append(f"{item} (unknown)")

  return "\n".join(items)

def cat(path: str) -> str:
  # if path is not a file in the current directory, return <FORBIDDEN>
  if not os.path.isfile(path):
    return "<FORBIDDEN>"

  try:
    # Convert both paths to real paths to handle symlinks, relative paths and drive issues
    abs_path = os.path.realpath(path)
    abs_cwd = os.path.realpath(os.getcwd())

    # Check if the path is within the current directory
    if not abs_path.startswith(abs_cwd + os.sep) and abs_path != abs_cwd:
      return "<FORBIDDEN>"
  except (ValueError, OSError):
    # Handle cases where paths are on different drives or other path issues
    return "<FORBIDDEN>"

  with open(path, "r", encoding="utf-8") as f:
    return f.read()

def tree(path: str, depth: int) -> str:
  if depth < 0:
    return ""
  if not os.path.isdir(path):
    return "<FORBIDDEN>"

  try:
    abs_path = os.path.realpath(path)
    abs_cwd = os.path.realpath(os.getcwd())
    if not abs_path.startswith(abs_cwd + os.sep) and abs_path != abs_cwd:
      return "<FORBIDDEN>"
  except (ValueError, OSError):
    return "<FORBIDDEN>"

  result = []
  for root, dirs, files in os.walk(path):
    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
    level = root.replace(path, "").count(os.sep)
    if level > depth:
      continue
    indent = " " * 4 * level
    result.append(f"{indent}{os.path.basename(root)}/")
    for f in files:
      if any(excluded in f for excluded in EXCLUDED_DIRS):
        continue
      result.append(f"{indent}    {f}")
  return "\n".join(result)


def grep(path: str, pattern: str) -> str:
  """Search for pattern in a file or recursively in a directory.

  Returns lines matching the pattern in the format:
    <relative_or_full_path>:<line_number>:<line>

  If path is not within the repository or does not exist, returns "<FORBIDDEN>".
  """
  if not path:
    return "<FORBIDDEN>"

  try:
    abs_path = os.path.realpath(path)
    abs_cwd = os.path.realpath(os.getcwd())
    if not abs_path.startswith(abs_cwd + os.sep) and abs_path != abs_cwd:
      return "<FORBIDDEN>"
  except (ValueError, OSError):
    return "<FORBIDDEN>"

  matches = []
  # If it's a file, search that file only
  if os.path.isfile(path):
    try:
      with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, start=1):
          if pattern in line:
            matches.append(f"{path}:{i}:{line.rstrip()}")
    except (OSError, IOError):
      # unreadable file -> return empty result
      return ""
    return "\n".join(matches)

  # If it's a directory, walk recursively
  if os.path.isdir(path):
    for root, dirs, files in os.walk(path):
      dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
      for fname in files:
        if any(excluded in fname for excluded in EXCLUDED_DIRS):
          continue
        fpath = os.path.join(root, fname)
        try:
          with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, start=1):
              if pattern in line:
                # use relative path for readability
                rel = os.path.relpath(fpath)
                matches.append(f"{rel}:{i}:{line.rstrip()}")
        except (OSError, IOError):
          # ignore unreadable files
          continue
    return "\n".join(matches)

  return "<FORBIDDEN>"
