from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess

@dataclass(frozen=True)
class CmdResult:
  cmd: list[str]
  returncode: int
  stdout: str
  stderr: str

class CmdError(RuntimeError):
  def __init__(self, result: CmdResult):
    super().__init__(f"Command failed: {result.cmd} (rc={result.returncode})")
    self.result = result

def run_cmd(repo: Path, cmd: list[str]) -> CmdResult:
  p = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
  res = CmdResult(cmd=cmd, returncode=p.returncode, stdout=p.stdout or "", stderr=p.stderr or "")
  if res.returncode != 0:
    raise CmdError(res)
  return res
