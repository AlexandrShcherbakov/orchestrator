from __future__ import annotations
import json
from pathlib import Path

from orchestrator.llm import LLM, LLMConfig
from orchestrator.bash_tools import cat, ls, tree, grep
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
      if context.step > 40:
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
          elif command.startswith("grep "):
            rest = command[5:].strip()
            if not rest:
              context.write_text(f"developer.txt", f"Invalid grep command: {command}")
              current_request = f"Invalid grep command: {command}. Please use the format: grep <path> <pattern>."
              break
            parts = rest.split(maxsplit=1)
            path = parts[0]
            pattern = parts[1] if len(parts) > 1 else ""
            command_result = grep(path, pattern)
            context.prompt_context[f"GREP_OUTPUT {path} {pattern}"] = command_result
            context.write_text(f"developer.txt", f"grep {path} {pattern}\n{command_result}")
            self.llm.clear_chat()
          else:
            context.write_text(f"developer.txt", f"Invalid command: {command}")
            current_request = f"Invalid command: {command}. Please use only the allowed commands: ls, cat, tree, grep."
            break
      else:
        print(f"Incorrect response status: {response.get('status')}")
        current_request = f"Invalid response status: {response.get('status')}. Add 'status' field with value 'complete' or 'need_more_info'."
