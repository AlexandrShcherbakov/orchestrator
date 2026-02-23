import os

EXCLUDED_DIRS = ['.git', '.venv', 'logs', '__pycache__', '*.pyc', '*.egg-info']

def ls(path: str) -> str:
  # if path is not a subdirectory of the current directory, return <FORBIDDEN>
  if not os.path.isdir(path):
    return "<FORBIDDEN>"

  try:
    # Convert both paths to absolute paths to handle relative paths and drive issues
    abs_path = os.path.abspath(path)
    abs_cwd = os.path.abspath(os.getcwd())

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
    # Convert both paths to absolute paths to handle relative paths and drive issues
    abs_path = os.path.abspath(path)
    abs_cwd = os.path.abspath(os.getcwd())

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
    abs_path = os.path.abspath(path)
    abs_cwd = os.path.abspath(os.getcwd())
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
