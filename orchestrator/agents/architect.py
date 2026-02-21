from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from orchestrator.llm import LLM
from orchestrator.task_logging import TaskLog

@dataclass(frozen=True)
class BootstrapResult:
  updated_files: list[str]
  problems: list[str]

@dataclass(frozen=True)
class ArchitectContext:
  """Контекст для работы архитектора с расширенной документацией."""
  docs_content: Dict[str, str]  # Имя файла -> содержимое
  repo_path: str
  total_docs: int

def create_architect_context(docs_content: Dict[str, str], repo: Path) -> ArchitectContext:
  """Создает контекст архитектора с собранной документацией."""
  return ArchitectContext(
    docs_content=docs_content,
    repo_path=str(repo),
    total_docs=len(docs_content)
  )

SYSTEM = """You are ArchitectBootstrap.
Rules:
- Be concise.
- Output MUST be valid YAML (no markdown, no code fences, no ```).
- You can only propose changes under docs/.
- If requirements are unclear, add items to problems.
"""

def run_architect_bootstrap(llm: LLM, repo: Path, log: TaskLog) -> BootstrapResult:
  facts = (repo / "docs" / "knowledge" / "facts.md").read_text(encoding="utf-8")

  user = f"""Project facts:
{facts}

Task:
1) Ensure docs/tasks/backlog.yaml, done.yaml, problems.yaml exist and are coherent.
2) Propose minimal updates to docs/architecture (if missing, create overview.md with 5-10 bullet points).
3) If anything blocks correctness, list questions.

Return YAML with keys:
updated_files: [list of paths]
proposed_changes:
  - path: docs/...
    content: |
      full new file content
problems: [list of questions]
"""

  out = llm.text(SYSTEM, user)
  log.write_text("architect_bootstrap_raw.yaml", out)

  # На этом шаге мы НЕ применяем изменения автоматически.
  # Только логируем предложение. Применение сделаем в следующем шаге.
  return BootstrapResult(updated_files=[], problems=[])
