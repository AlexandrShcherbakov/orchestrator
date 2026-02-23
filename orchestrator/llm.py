from __future__ import annotations
import os
from dataclasses import dataclass

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LLMConfig:
  model: str = "gpt-5-mini"  # поменяем позже вместе с архитектором
  max_output_tokens: int = 1200


class LLM:
  def __init__(self, cfg: LLMConfig, system: str):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
      raise RuntimeError("OPENAI_API_KEY is not set")
    self.client = OpenAI(api_key=api_key)
    self.cfg = cfg
    self.chat = [{"role": "system", "content": system}]

  def text(self, context: dict[str, str], user: str, commit_message: bool) -> str:
    user_msg = "\n".join(f"{k}:\n{v}" for k, v in context.items())
    user_msg += f"\n\n{user}"
    if commit_message:
      self.chat.append({"role": "user", "content": user_msg})
      input_chain = self.chat
    else:
      input_chain = self.chat + [{"role": "user", "content": user_msg}]
    # Responses API
    resp = self.client.responses.create(
      model=self.cfg.model,
      input=input_chain,
      max_output_tokens=self.cfg.max_output_tokens,
    )
    # SDK convenience field: output_text
    output_message = getattr(resp, "output_text", "") or ""
    if output_message == "":
      print("Warning: LLM response is empty")
    if commit_message:
      self.chat.append({"role": "assistant", "content": output_message})
    return output_message

  def confirm_assistant(self, new_assistant: str):
    self.chat.append({"role": "assistant", "content": new_assistant})
