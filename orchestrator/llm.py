from __future__ import annotations
import os
from dataclasses import dataclass

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LLMConfig:
  model: str = "gpt-4o-mini"  # поменяем позже вместе с архитектором
  max_output_tokens: int = 1200


class LLM:
  def __init__(self, cfg: LLMConfig):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
      raise RuntimeError("OPENAI_API_KEY is not set")
    self.client = OpenAI(api_key=api_key)
    self.cfg = cfg

  def text(self, system: str, user: str) -> str:
    # Responses API
    resp = self.client.responses.create(
      model=self.cfg.model,
      input=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
      ],
      max_output_tokens=self.cfg.max_output_tokens,
    )
    # SDK convenience field: output_text
    return getattr(resp, "output_text", "") or ""
