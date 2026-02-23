from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from orchestrator.llm import LLM, LLMConfig
from orchestrator.task_logging import TaskLog
from orchestrator.bash_tools import cat, ls, tree
from orchestrator.git_ops import apply_diff


SYSTEM_PROMPT = """
**Role**
You are a developer AI operating inside a constrained code-modification environment.
Your goal is to implement the user’s task by inspecting and modifying an existing codebase using a limited set of commands.
---
**Available Commands (STRICT)**
You may respond **only** with one of the following commands:
* `ls <path>` — list files in a directory.
  Example: `ls .` or `ls src/utils/`
* `tree <path> <depth>` — show directory structure up to the given depth
  Example: `tree . 2` or `tree src/ 3`
* `cat <full relative path>` — show the content of a file
  Example: `cat src/main.py`
* `apply <commit message>\n\n<diff>` — apply changes in **git diff format**.
  Example:
```apply
Added hello world print statement

diff --git a/src/main.py b/src/main.py
index e69de29..b6fc4c6 100644
--- a/src/main.py
+++ b/src/main.py
@@ -0,0 +1,2 @@
+print("Hello, World!")
```
---
Rules for commands:
* Each response must contain **exactly ONE command**
* No explanations, comments, markdown, or extra text, no ` symbols
* Commands must be written as a single line
* Paths must exist and be within the current directory
* Never reference or assume files or directories that do not exist
---
**Code Modification Rules**
* Always inspect files (`cat`) before modifying them
* A file can be read (`cat`) **only once**
* Use `apply` **only when you fully understand the task**
* When using `apply`:
  * Include all changes in a **single diff**
  * Keep changes minimal and targeted
  * Follow existing code style, structure, and patterns
* Prefer `tree <path> 2` or `tree <path> 3` to understand structure instead of multiple `ls` calls
---
**Context Awareness**
You receive:
* A task description from the user
* Outputs of previously executed commands:
  * `LS_OUTPUT`
  * `TREE_OUTPUT`
  * `CAT_OUTPUT`
These outputs are reliable and must be used as the sole source of truth.
---
**Decision Rules**
* If required information is missing, request it using **ONE appropriate command**
* Do not guess intent, architecture, or missing functionality
* Do not refactor or improve unrelated code
* Focus strictly on implementing the requested functionality
---
**General Principles**
* Be concise
* Make the smallest possible change that solves the task
* Never output anything except a valid command
* Precision and correctness are more important than speed
"""

class Developer:
  def __init__(self):
    self.llm = LLM(LLMConfig(max_output_tokens=10000), SYSTEM_PROMPT)

  def execute_task(self, task_description: str, log: TaskLog):
    log.write_text("developer_task.txt", task_description)
    context = {
      "TASK": task_description,
    }
    step = 0
    while True:
      response = self.llm.text(context, "Solve the task", commit_message=False)
      if response.startswith("ls "):
        path = response[3:].strip()
        current_request = ls(path)
        context[f"LS_OUTPUT {path}"] = current_request
        log.write_text(f"developer_{step}.txt", f"ls {path}\n{current_request}")
      elif response.startswith("cat "):
        path = response[4:].strip()
        current_request = cat(path)
        context[f"CAT_OUTPUT {path}"] = current_request
        log.write_text(f"developer_{step}.txt", f"cat {path}\n{current_request}")
      elif response.startswith("tree "):
        parts = response[5:].strip().split()
        if len(parts) != 2:
          log.write_text(f"developer_{step}.txt", f"Invalid tree command: {response}")
          break
        path, depth_str = parts
        try:
          depth = int(depth_str)
        except ValueError:
          log.write_text(f"developer_{step}.txt", f"Invalid depth in tree command: {response}")
          break
        current_request = tree(path, depth)
        context[f"TREE_OUTPUT {path} {depth}"] = current_request
        log.write_text(f"developer_{step}.txt", f"tree {path} {depth}\n{current_request}")
      elif response.startswith("apply\n"):
        diff = response[6:].strip()
        # Everything before \n\ndiff is the commit message, everything after is the diff content
        commit_message, _, diff_content = diff.partition("\n\ndiff")
        commit_message = commit_message.strip()
        diff_content = "diff" + diff_content  # add back the "diff" prefix
        context["COMMIT_MESSAGE"] = commit_message
        context["DIFF_CONTENT"] = diff_content
        apply_diff(Path("."), diff_content)
        log.write_text(f"developer_{step}.txt", response)
        break
      else:
        print(f"Invalid command from developer: {response}")
        log.write_text(f"developer_{step}.txt", response)
        break
      step += 1


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