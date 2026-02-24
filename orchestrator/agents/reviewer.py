from __future__ import annotations
import json
from pathlib import Path

from orchestrator.llm import LLM, LLMConfig
from orchestrator.task_logging import TaskLog
from orchestrator.bash_tools import cat, ls, tree
from orchestrator.agents.reviewer_prompt import SYSTEM_PROMPT


class Reviewer:
  def __init__(self):
    self.llm = LLM(LLMConfig(max_output_tokens=10000), SYSTEM_PROMPT)

  def review_task(self, repo: Path, context: dict[str, str], log: TaskLog):

    step = -1
    current_request = (
      "Review the proposed changes and produce concise, specific comments that point to exact "
      "places in the diff (file path and line ranges). Follow the required JSON schema exactly."
    )

    while True:
      step += 1
      if step > 100:
        log.write_text("reviewer_final.txt", "Exceeded maximum number of steps without producing a valid review.")
        break
      try:
        raw_response = self.llm.text(context, current_request)
        response = json.loads(raw_response)
        log.write_json(f"reviewer_{step}.txt", {"LLM Response": response})
        step += 1
      except json.JSONDecodeError as e:
        log.write_text(f"reviewer_{step}.txt", f"Failed to parse LLM response as JSON: {e}\nResponse was:\n{raw_response}")
        current_request = f"Failed to parse your response as JSON: {e}\nPlease ensure your response strictly follows the JSON schema and contains no extra text."
        continue
      status = response.get("status", "")
      if status == "complete":
        comments = response.get("comments", [])
        invalid = None
        if not isinstance(comments, list):
          invalid = "'comments' must be a list"
        else:
          for i, c in enumerate(comments):
            if not isinstance(c, dict):
              invalid = f"Comment at index {i} is not an object"
              break
            required_keys = {"path", "start_line", "end_line", "comment", "severity"}
            if not required_keys.issubset(set(c.keys())):
              missing = required_keys - set(c.keys())
              invalid = f"Comment at index {i} is missing keys: {sorted(list(missing))}"
              break
            if c.get("severity") not in ("info", "warning", "error"):
              invalid = f"Invalid severity in comment at index {i}: {c.get('severity')}"
              break
            try:
              int(c.get("start_line"))
              int(c.get("end_line"))
            except Exception:
              invalid = f"start_line and end_line must be integers in comment at index {i}"
              break
        if invalid:
          log.write_text(f"reviewer_{step}.txt", invalid)
          current_request = f"{invalid}. Please return a JSON object strictly following the schema."
          continue
        log.write_json("reviewer_final.json", response)
        summary = [f"Reviewer finished with {len(comments)} comment(s)."]
        for c in comments:
          if c["severity"] == "error":
            summary.append(f"{c['path']}:{c['start_line']}-{c['end_line']} [{c['severity']}]: {c['comment']}")
        context["REVIEW_SUMMARY"] = "\n".join(summary)
        log.write_text("reviewer_final.txt", "\n".join(summary))
        break
      elif status == "need_more_info":
        for command in response.get("commands", []):
          if command.startswith("ls "):
            path = command[3:].strip()
            command_result = ls(path)
            context[f"LS_OUTPUT {path}"] = command_result
            log.write_text(f"reviewer_{step}.txt", f"ls {path}\n{command_result}")
            self.llm.clear_chat()
          elif command.startswith("cat "):
            path = command[4:].strip()
            command_result = cat(path)
            context[f"CAT_OUTPUT {path}"] = command_result
            log.write_text(f"reviewer_{step}.txt", f"cat {path}\n{command_result}")
            self.llm.clear_chat()
          elif command.startswith("tree "):
            parts = command[5:].strip().split()
            if len(parts) != 2:
              log.write_text(f"reviewer_{step}.txt", f"Invalid tree command: {command}")
              current_request = f"Invalid tree command: {command}. Please use the format: tree <path> <depth>."
              break
            path, depth_str = parts
            try:
              depth = int(depth_str)
            except ValueError:
              log.write_text(f"reviewer_{step}.txt", f"Invalid depth in tree command: {command}")
              current_request = f"Invalid depth in tree command: {command}. Depth must be an integer."
              break
            command_result = tree(path, depth)
            context[f"TREE_OUTPUT {path} {depth}"] = command_result
            log.write_text(f"reviewer_{step}.txt", f"tree {path} {depth}\n{command_result}")
            self.llm.clear_chat()
          else:
            log.write_text(f"reviewer_{step}.txt", f"Invalid command: {command}")
            current_request = f"Invalid command: {command}. Please use only the allowed commands: ls, cat, tree."
            break
      else:
        log.write_text(f"reviewer_{step}.txt", f"Incorrect response status: {status}")
        current_request = f"Invalid response status: {status}. Add 'status' field with value 'complete' or 'need_more_info'."
