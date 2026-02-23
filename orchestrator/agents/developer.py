from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from orchestrator.llm import LLM, LLMConfig
from orchestrator.task_logging import TaskLog
from orchestrator.bash_tools import cat, ls, tree


SYSTEM_PROMPT = """
You are developer. You get a task from a user and need to modify code to solve it.
Allowed responses from you:
ls <path> - list files in a directory
tree <path> <depth> - show directory structure up to depth levels
cat <full relative path> - show file content
apply <diff> - apply changes to files in git diff format. Keep the diff short. You should show the diff for all the tasks at the same response, do not break it into multiple responses. You can use this command only when you are ready to implement the task and have a clear understanding of what needs to be done.
You are not allowed to use any other commands.
Commands should we written as a single command without any comments. Do not explain your commands, just write them.
It is always better to get a tree with 2/3 levels to understand the structure of the codebase instead of asking for ls multiple times.

If you don't have enough data, use commands (ONE COMMAND FOR A SINGLE RESPONSE).
You should read the file before you modify it.

From the user you receive a task desciption and results of some commands executed earlier.

Rules:
- Be concise.
- Focus on small, targeted changes that implement the specific functionality.
- Consider existing code structure and patterns.
- Apply commands only to files/dirs that exist and are within the current directory.
- Do not imagine files that do not exist, you can only work with existing files and directories.
- Results of previous ls, cat and tree commands are available in the context (LS_OUTPUT, FILE, TREE_OUTPUT) for you to analyze and make decisions based on them.
- Output MUST be a SINGLE valid command in described formats (no markdown, no code fences, no ```).
"""

class Developer:
  def __init__(self):
    self.llm = LLM(LLMConfig(), SYSTEM_PROMPT)

  def execute_task(self, task_description: str, log: TaskLog):
    log.write_text("developer_task.txt", task_description)
    context = {}
    current_request = task_description
    while True:
      response = self.llm.text(context, current_request, commit_message=True)
      if response.startswith("ls "):
        path = response[3:].strip()
        current_request = ls(path)
        log.write_text("developer_ls.txt", f"ls {path}\n{current_request}")
      elif response.startswith("cat "):
        path = response[4:].strip()
        current_request = cat(path)
        log.write_text("developer_cat.txt", f"cat {path}\n{current_request}")
      elif response.startswith("tree "):
        parts = response[5:].strip().split()
        if len(parts) != 2:
          log.write_text("developer_response.txt", f"Invalid tree command: {response}")
          break
        path, depth_str = parts
        try:
          depth = int(depth_str)
        except ValueError:
          log.write_text("developer_response.txt", f"Invalid depth in tree command: {response}")
          break
        current_request = tree(path, depth)
        log.write_text("developer_tree.txt", f"tree {path} {depth}\n{current_request}")
      elif response.startswith("request_impl "):
        request = response[len("request_impl "):].strip()
        log.write_text("developer_request_impl.txt", f"request_impl\n{request}")
        print(f"Developer requests implementation: {request}")
        break
      elif response.startswith("apply "):
        diff = response[6:].strip()
        log.write_text("developer_apply.txt", f"apply\n{diff}")
        break
      else:
        print(f"Invalid command from developer: {response}")
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