import os

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

  return "\n".join(os.listdir(path))

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
