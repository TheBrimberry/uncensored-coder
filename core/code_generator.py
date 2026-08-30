import os
import re
import logging
from enum import Enum

from .model_loader import ModelLoader
from .openai_loader import OpenAIModelLoader
from .prompt_templates import PromptTemplates


class SupportedLanguage(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    RUST = "rust"
    GO = "go"
    HTML = "html"
    CSS = "css"
    SQL = "sql"


class CodeGenerator:
    def __init__(self, model: str = "deepseek-coder:6.7b", enable_logging: bool = True, provider: str = None):
        self.provider = (provider or os.getenv("AI_PROVIDER", "ollama")).lower()
        self.model_name = model
        self.logger = self._setup_logger(enable_logging)

        try:
            if self.provider == "openai":
                openai_model = os.getenv("OPENAI_MODEL") or None
                self.loader = OpenAIModelLoader(openai_model)
                self.model_name = self.loader.model_name
            elif self.provider == "ollama":
                self.loader = ModelLoader(model)
            else:
                raise ValueError("AI_PROVIDER must be 'ollama' or 'openai'")
            self.templates = PromptTemplates()
        except Exception as e:
            raise RuntimeError(f"Initialization Error: {e}") from e

    def _setup_logger(self, enable: bool):
        logger = logging.getLogger(__name__)
        if enable and not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(h)
            logger.setLevel(logging.INFO)
        return logger

    def _clean_code(self, text: str) -> str:
        """Remove a surrounding markdown code fence when the response is code-only."""
        pattern = r"```(?:\w+)?\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    def generate(self, user_request: str, language: str = "python") -> str:
        system_p = self.templates.get_system_prompt(language)
        user_p = self.templates.get_user_prompt(user_request, language)
        return self._clean_code(self.loader.generate(user_p, system_prompt=system_p))

    def save_to_file(self, code: str, filename: str) -> str:
        os.makedirs("generated_code", exist_ok=True)
        path = os.path.join("generated_code", filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return path
