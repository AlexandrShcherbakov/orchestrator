from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
from orchestrator.task_logging import TaskLog


@dataclass(frozen=True)
class Step:
  name: str
  actor: str               # "orchestrator", "developer", ...
  context_summary: str     # коротко: что передаём/что делаем
  run: Callable[[], Any]   # действие шага


def run_step(step: Step, log: TaskLog, interactive: bool, index: int, total: int) -> Any:
  header = f"STEP {index}/{total}: {step.name} [{step.actor}]"
  print(header)
  print(f"context: {step.context_summary}")

  log.write_text(f"{index:02d}_{step.name}_meta.txt", header + "\n" + step.context_summary + "\n")

  if interactive:
    while True:
      cmd = input("command (next/abort): ").strip().lower()
      if cmd == "next":
        break
      if cmd == "abort":
        raise SystemExit(130)

  result = step.run()
  log.write_text(f"{index:02d}_{step.name}_result.txt", str(result) if result is not None else "")
  return result
