from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from orchestrator.llm import LLM, LLMConfig
from orchestrator.task_logging import TaskLog
from orchestrator.bash_tools import cat, ls


SYSTEM_PROMPT = """
You are developer. You get a task from a user and need to modify code to solve it.
Allowed responses from you:
ls <path> - list files in a directory
cat <path> - show file content
apply <diff> - apply changes to files in git diff format.
You are not allowed to use any other commands.
Commands should we written as a single command without any comments. Do not explain your commands, just write them.

Rules:
- Be concise.
- Focus on small, targeted changes that implement the specific functionality.
- Consider existing code structure and patterns.
"""

class Developer:
  def __init__(self):
    self.llm = LLM(LLMConfig(), SYSTEM_PROMPT)

  def execute_task(self, task_description: str, log: TaskLog):
    log.write_text("developer_task.txt", task_description)
    context = {
      "TASK": task_description,
    }
    while True:
      response = self.llm.text(context, "Solve the task", commit_message=False)
      if response.startswith("ls "):
        path = response[3:].strip()
        context[f"LS_OUTPUT for {path}"] = ls(path)
        log.write_text("developer_ls.txt", f"ls {path}\n{context[f'LS_OUTPUT for {path}']}")
      elif response.startswith("cat "):
        path = response[4:].strip()
        context[f"FILE for {path}"] = cat(path)
        log.write_text("developer_cat.txt", f"cat {path}\n{context[f'FILE for {path}']}")
      elif response.startswith("apply "):
        diff = response[6:].strip()
        log.write_text("developer_apply.txt", f"apply\n{diff}")
        break
      else:
        log.write_text("developer_response.txt", response)
        break


@dataclass(frozen=True)
class DeveloperContext:
  """Контекст для работы разработчика с задачей и тестами."""
  task_context: Dict[str, str]  # Имя файла -> содержимое
  test_proposals: list[str]  # Предложения тестов
  repo_path: str
  total_files: int

def create_developer_context(task_context: Dict[str, str], test_proposals: list[str], repo: Path) -> DeveloperContext:
  """Создает контекст разработчика."""
  return DeveloperContext(
    task_context=task_context,
    test_proposals=test_proposals,
    repo_path=str(repo),
    total_files=len(task_context)
  )

@dataclass(frozen=True)
class DeveloperResult:
  """Результат работы разработчика."""
  proposal_yaml: str
  implementation_ready: bool

SYSTEM = """You are Developer.
Rules:
- Be concise.
- Output MUST be valid YAML (no markdown, no code fences, no ```).
- You can propose changes to any files except tests/ and docs/tests/.
- Implement the task requirements to make tests pass.
- Focus on small, targeted changes that implement the specific functionality.
- Consider existing code structure and patterns.
"""

def run_developer(llm: LLM, developer_context: DeveloperContext, log: TaskLog) -> str:
  """Запускает разработчика для реализации задачи."""

  # Формируем контекст для разработчика
  context_text = "Task context:\n\n"
  for filename, content in developer_context.task_context.items():
    context_text += f"=== {filename} ===\n{content}\n\n"

  test_proposals_text = "Test proposals:\n\n"
  for i, proposal in enumerate(developer_context.test_proposals, 1):
    test_proposals_text += f"=== Test Proposal {i} ===\n{proposal}\n\n"

  user_prompt = f"""Implement the task to make the proposed tests pass.

{context_text}

{test_proposals_text}

Generate a proposal to implement the required functionality.

Requirements:
- Analyze the task and test requirements
- Implement minimal code changes to make tests pass
- Follow existing code patterns and structure
- Do not modify test files

Generate YAML with proposed_changes containing implementation."""

  response = llm.text(SYSTEM, user_prompt)

  # Логируем запрос и ответ
  log.write_text("developer_request.txt", user_prompt)
  log.write_text("developer_response.txt", response)

  return response