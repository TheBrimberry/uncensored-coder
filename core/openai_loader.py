"""OpenAI provider for the Uncensored Coder workspace.

This keeps the existing Ollama provider intact and provides an optional
ChatGPT/OpenAI path selected with AI_PROVIDER=openai.
"""

import os
from typing import Optional

from openai import OpenAI


class OpenAIModelLoader:
    def __init__(self, model_name: Optional[str] = None):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-5")
        self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        instructions = system_prompt or (
            "You are the ChatGPT coding provider inside a developer workspace. "
            "Produce accurate, complete, maintainable code and concise implementation notes."
        )
        response = self.client.responses.create(
            model=self.model_name,
            instructions=instructions,
            input=prompt,
        )
        return response.output_text
