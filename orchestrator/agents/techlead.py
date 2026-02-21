from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
import yaml
from orchestrator.llm import LLM
from orchestrator.task_logging import TaskLog

@dataclass(frozen=True)
class TechleadContext:
  """Контекст для работы техлида с документацией и беклогом."""
  docs_content: Dict[str, str]  # Имя файла -> содержимое
  repo_path: str
  total_docs: int

def create_techlead_context(context_data: Dict[str, str], repo: Path) -> TechleadContext:
  """Создает контекст техлида с собранной документацией и беклогом."""
  return TechleadContext(
    docs_content=context_data,
    repo_path=str(repo),
    total_docs=len(context_data)
  )

@dataclass(frozen=True)
class TechleadResult:
  """Результат работы техлида."""
  proposal_yaml: str
  subtasks_created: int

SYSTEM = """You are TechLead.
Rules:
- Be concise.
- Output MUST be valid YAML (no markdown, no code fences, no ```).
- You can only modify files under docs/.
- Break down large tasks into smaller subtasks when necessary.
- Each subtask should result in less than 300 lines of changes.
- Only modify backlog.yaml and architecture md files.
- Create specific, actionable subtasks with clear dependencies.
"""

def run_techlead(llm: LLM, techlead_context: TechleadContext, log: TaskLog) -> str:
  """Запускает техлида для разбора задач на подзадачи."""

  # Формируем контекст для техлида
  context_text = "Current documentation and backlog:\n\n"
  for filename, content in techlead_context.docs_content.items():
    context_text += f"=== {filename} ===\n{content}\n\n"

  user_prompt = f"""Analyze the current backlog and break down large tasks into smaller subtasks if needed.

Requirements:
- Each subtask should be implementable in <300 lines of code changes
- Tasks should have clear dependencies
- Focus on keeping commits small and focused
- Update backlog.yaml with new subtasks

{context_text}

Generate a proposal to update the backlog with properly sized subtasks."""

  response = llm.call_llm(SYSTEM, user_prompt)

  # Логируем запрос и ответ
  log.write_text("techlead_request.txt", user_prompt)
  log.write_text("techlead_response.txt", response)

  return response