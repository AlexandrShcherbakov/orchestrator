from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict

from orchestrator.llm import LLM, LLMConfig
from orchestrator.task_logging import TaskLog
from orchestrator.bash_tools import cat, ls, tree
from orchestrator.execution_context import Context
from orchestrator.agents.developer_prompt import SYSTEM_PROMPT


class Developer:
  def __init__(self):
    self.llm = LLM(LLMConfig(max_output_tokens=10000), SYSTEM_PROMPT)
    self.task_started = False

  def execute_task(self, repo: Path, context: Context):
    current_request = "Solve the task" if not self.task_started else "Check review comments and update implementation if needed"
    self.task_started = True
    while True:
      if context.step > 200:
        context.write_text("developer_final.txt", "Exceeded maximum number of steps without producing a valid implementation.")
        break
      try:
        raw_response = self.llm.text(context.prompt_context, current_request)
        response = json.loads(raw_response)
        context.write_json(f"developer.txt", {"LLM Response": response})
      except json.JSONDecodeError as e:
        context.write_text(f"developer.txt", f"Failed to parse LLM response as JSON: {e}\nResponse was:\n{raw_response}")
        current_request = f"Failed to parse your response as JSON: {e}\nPlease ensure your response strictly follows the JSON schema and contains no extra text."
        continue
      if response.get("status", "") == "complete":
          context.prompt_context["COMMIT_MESSAGE"] = response["commit_message"]
          context.prompt_context["NEW_CONTENT"] = json.dumps(response["changes"])
          context.set_commit_candidate(response["commit_message"], response["changes"])
          if "REVIEW_SUMMARY" in context.prompt_context:
              del context.prompt_context["REVIEW_SUMMARY"]
          break
      elif response.get("status", "") == "need_more_info":
        for command in response["commands"]:
          if command.startswith("ls "):
            path = command[3:].strip()
            command_result = ls(path)
            context.prompt_context[f"LS_OUTPUT {path}"] = command_result
            context.write_text(f"developer.txt", f"ls {path}\n{command_result}")
            self.llm.clear_chat()
          elif command.startswith("cat "):
            path = command[4:].strip()
            command_result = cat(path)
            context.prompt_context[f"CAT_OUTPUT {path}"] = command_result
            context.write_text(f"developer.txt", f"cat {path}\n{command_result}")
            self.llm.clear_chat()
          elif command.startswith("tree "):
            parts = command[5:].strip().split()
            if len(parts) != 2:
              context.write_text(f"developer.txt", f"Invalid tree command: {command}")
              current_request = f"Invalid tree command: {command}. Please use the format: tree <path> <depth>."
              break
            path, depth_str = parts
            try:
              depth = int(depth_str)
            except ValueError:
              context.write_text(f"developer.txt", f"Invalid depth in tree command: {command}")
              current_request = f"Invalid depth in tree command: {command}. Depth must be an integer."
              break
            command_result = tree(path, depth)
            context.prompt_context[f"TREE_OUTPUT {path} {depth}"] = command_result
            context.write_text(f"developer.txt", f"tree {path} {depth}\n{command_result}")
            self.llm.clear_chat()
          else:
            context.write_text(f"developer.txt", f"Invalid command: {command}")
            current_request = f"Invalid command: {command}. Please use only the allowed commands: ls, cat, tree."
            break
      else:
        print(f"Incorrect response status: {response.get('status')}")
        current_request = f"Invalid response status: {response.get('status')}. Add 'status' field with value 'complete' or 'need_more_info'."


@dataclass(frozen=True)
class DeveloperContext:
  """Context for the developer working on the task and tests."""
  task_context: Dict[str, str]  # Filename -> content
  test_proposals: list[str]  # Test proposals
  repo_path: str
  total_files: int

def create_developer_context(task_context: Dict[str, str], test_proposals: list[str], repo: Path) -> DeveloperContext:
  """Creates developer context."""
  return DeveloperContext(
    task_context=task_context,
    test_proposals=test_proposals,
    repo_path=str(repo),
    total_files=len(task_context)
  )

@dataclass(frozen=True)
class DeveloperResult:
  """Result of the developer's work."""
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
  """Runs the developer to implement the task."""

  # Build context for the developer
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

  # Log the request and response
  log.write_text("developer_request.txt", user_prompt)
  log.write_text("developer_response.txt", response)

  return response
