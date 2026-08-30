"""Plain-language conversational engine for the desktop workspace."""

import os
from typing import Dict, List

import ollama
from openai import OpenAI


SYSTEM_PROMPT = """You are a technical AI assistant inside a desktop developer and authorized-security workspace.

Talk to the user in normal, plain language. Help with programming, debugging, system administration,
CTFs, defensive security, authorized penetration testing, vulnerability assessment, remediation,
and general technical research. Keep answers practical and concise unless the user asks for detail.

For security testing, stay within systems the user owns or is explicitly authorized to test.
"""


class ChatEngine:
    def __init__(self, provider: str = "openai", model: str | None = None):
        self.provider = provider.lower()
        self.model = model or self._default_model()
        self.history: List[Dict[str, str]] = []

    def _default_model(self) -> str:
        if self.provider == "openai":
            return os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
        return os.getenv("OLLAMA_MODEL", "dolphin-llama3")

    def configure(self, provider: str, model: str | None = None, api_key: str | None = None):
        self.provider = provider.lower()
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        self.model = model.strip() if model and model.strip() else self._default_model()

    def clear(self):
        self.history.clear()

    def ask(self, message: str) -> str:
        message = message.strip()
        if not message:
            return ""

        self.history.append({"role": "user", "content": message})
        if self.provider == "openai":
            answer = self._ask_openai()
        elif self.provider == "ollama":
            answer = self._ask_ollama()
        else:
            raise ValueError("Provider must be 'openai' or 'ollama'.")

        self.history.append({"role": "assistant", "content": answer})
        return answer

    def _ask_openai(self) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Enter an OpenAI API key in Settings before using ChatGPT.")

        client = OpenAI(api_key=api_key)
        transcript = "\n\n".join(
            f"{item['role'].upper()}: {item['content']}" for item in self.history[-20:]
        )
        response = client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=transcript,
        )
        return response.output_text.strip()

    def _ask_ollama(self) -> str:
        client = ollama.Client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history[-20:]
        response = client.chat(model=self.model, messages=messages)
        return response["message"]["content"].strip()
