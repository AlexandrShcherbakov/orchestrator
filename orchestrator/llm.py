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
    self.chat: list[dict[str, str]] = []
    self.system = {"role": "system", "content": system}
    self.last_request_response_pair = None

  def text(self, context: dict[str, str], user: str) -> str:
    config_msg = "\n".join(f"{k}:\n{v}" for k, v in context.items())
    input_chain = [
      self.system,
      {"role": "user", "content": config_msg},
    ] + self.chat + [{"role": "user", "content": user}]
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
    self.last_request_response_pair = (user, output_message)
    return output_message

  def confirm_chat(self):
    self.chat.append({"role": "user", "content": self.last_request_response_pair[0]})
    self.chat.append({"role": "assistant", "content": self.last_request_response_pair[1]})
    self.last_request_response_pair = None
