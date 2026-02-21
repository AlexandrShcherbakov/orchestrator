from __future__ import annotations
from pathlib import Path

from orchestrator.llm import LLM
from orchestrator.task_logging import TaskLog  # если вы переименовали logging.py
# если файл назвали иначе — поправьте импорт


SYSTEM = """You are Tester.
Rules:
- Be concise.
- Output MUST be valid YAML (no markdown, no code fences).
- Only propose changes in tests/ or docs/tests/.
- Prefer minimal tests that fail before and pass after implementation.
"""


def run_tester(llm: LLM, repo: Path, task_id: str, title: str, description: str, facts: str, log: TaskLog) -> str:
  user = f"""Task:
id: {task_id}
title: {title}
description: |
{description}

Project facts:
{facts}

Return YAML:
proposed_changes:
  - path: tests/...
    content: |
      ...
problems: []
"""
  out = llm.text(SYSTEM, user)
  log.write_text("tester_raw.yaml", out)
  return out
