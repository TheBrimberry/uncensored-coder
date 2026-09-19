"""
Code generation orchestration.

Author: JAZZYLYFE
"""

import os
import re
import logging
from typing import Optional

from .model_loader import ModelLoader, OllamaUnavailableError
from .prompt_templates import PromptTemplates

# Re-export so callers can catch it from a single module.
__all__ = ["CodeGenerator", "OllamaUnavailableError"]


class CodeGenerator:
    def __init__(self, model: str = "dolphin-llama3", enable_logging: bool = True):
        self.model_name = model
        self.logger = self._setup_logger(enable_logging)
        try:
            self.loader = ModelLoader(model)
            self.templates = PromptTemplates()
        except OllamaUnavailableError:
            # Let readiness errors bubble up untouched so the caller can show a
            # precise, actionable message.
            raise
        except Exception as e:
            raise RuntimeError(f"Initialization Error: {e}")

    def _setup_logger(self, enable: bool):
        logger = logging.getLogger(__name__)
        if enable and not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(h)
            logger.setLevel(logging.INFO)
        return logger

    def ensure_ready(self) -> bool:
        """Make sure the target model is available locally, pulling it if
        needed. Raises OllamaUnavailableError with an actionable message when
        the server is unreachable."""
        self.logger.info("Checking model availability: %s", self.model_name)
        return self.loader.pull_model()

    def _clean_code(self, text: str) -> str:
        """Removes markdown code fences and returns raw code only."""
        pattern = r"```(?:\w+)?\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    def generate(self, user_request: str, language: str = "python") -> str:
        # Send the system mandate as a real system message (previously it was
        # concatenated into the user prompt, weakening its effect on the model).
        system_p = self.templates.get_system_prompt(language)
        user_p = self.templates.get_user_prompt(user_request, language)

        raw_code = self.loader.generate(user_p, system_prompt=system_p)
        return self._clean_code(raw_code)

    def save_to_file(self, code: str, filename: str) -> str:
        os.makedirs("generated_code", exist_ok=True)
        path = os.path.join("generated_code", filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return path
