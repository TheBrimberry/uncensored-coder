"""
Gestisce il caricamento e l'interazione con i modelli Ollama.

Author: JAZZYLYFE
"""

import os
from typing import Optional

import yaml

try:  # ollama is an optional runtime dependency; import lazily-friendly
    import ollama
except ImportError:  # pragma: no cover - exercised only without the dep
    ollama = None


class OllamaUnavailableError(RuntimeError):
    """Raised when the local Ollama server cannot be reached."""


def _model_identifier(entry) -> str:
    """Extract a model name from an Ollama ``list()`` entry.

    Ollama's Python client has changed shape across versions:

    * ``>=0.4`` returns pydantic ``ListResponse.Model`` objects whose field is
      ``model`` (e.g. ``"dolphin-llama3:latest"``) and *not* ``name``.
    * older releases returned plain ``dict`` entries keyed by ``name``.

    Reading only ``name`` (as the previous implementation did) always yielded
    an empty string on modern clients, so the model was *never* detected as
    installed. This helper handles both object- and dict-style entries.
    """
    for key in ("model", "name"):
        # dict-style access
        if isinstance(entry, dict):
            value = entry.get(key)
        else:
            # object / pydantic style access; ollama models are subscriptable
            value = getattr(entry, key, None)
        if value:
            return str(value)
    return ""


class ModelLoader:
    def __init__(self, model_name: Optional[str] = None):
        # Carichiamo la configurazione dallo YAML per non avere dati cablati
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "model_config.yaml"
        )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ Errore caricamento config: {e}")
            self.config = {}

        # Priorità: 1. Argomento passato | 2. Default da YAML | 3. Hardcoded fallback
        self.model_name = model_name or self.config.get("default_model", "dolphin-llama3")

        if ollama is None:
            raise OllamaUnavailableError(
                "The 'ollama' package is not installed. Run 'pip install ollama' "
                "and make sure the Ollama server is running (https://ollama.com)."
            )
        self.client = ollama.Client()

    def is_model_available(self) -> bool:
        """Verifica se il modello è già scaricato."""
        try:
            response = self.client.list()
        except Exception as e:
            raise OllamaUnavailableError(
                "Could not reach the Ollama server. Is it running? "
                "Start it with 'ollama serve'."
            ) from e

        # ollama >=0.4 returns a ListResponse (attribute access); older
        # versions returned a plain dict. Support both.
        if isinstance(response, dict):
            model_list = response.get("models", []) or []
        else:
            model_list = getattr(response, "models", []) or []

        # Match with or without the ":tag" suffix so "dolphin-llama3" matches
        # an installed "dolphin-llama3:latest".
        wanted = self.model_name.split(":")[0]
        for entry in model_list:
            installed = _model_identifier(entry)
            if not installed:
                continue
            if installed == self.model_name or installed.split(":")[0] == wanted:
                return True
        return False

    def pull_model(self) -> bool:
        """Scarica il modello se non presente. Ritorna True se disponibile."""
        if self.is_model_available():
            return True

        print(f"📥 Modello {self.model_name} non trovato. Download in corso...")
        try:
            self.client.pull(self.model_name)
            print("✅ Download completato!")
            return True
        except Exception as e:
            raise OllamaUnavailableError(
                f"Errore durante il download del modello '{self.model_name}': {e}"
            ) from e

    def _generation_options(self) -> dict:
        """Build the Ollama options dict from config, forwarding every
        supported generation parameter (not just a subset)."""
        gen = self.config.get("generation", {}) or {}
        options = {
            "temperature": gen.get("temperature", 0.1),
            "top_p": gen.get("top_p", 0.9),
            "num_predict": gen.get("max_tokens", 2048),
        }
        # Optional params: only forward when present so we don't override
        # sensible Ollama defaults with None.
        for cfg_key, opt_key in (
            ("top_k", "top_k"),
            ("presence_penalty", "presence_penalty"),
            ("frequency_penalty", "frequency_penalty"),
        ):
            if gen.get(cfg_key) is not None:
                options[opt_key] = gen[cfg_key]
        return options

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Genera una risposta dal modello con i parametri dello YAML."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options=self._generation_options(),
            )
        except Exception as e:
            raise OllamaUnavailableError(
                "Generation failed. Ensure the Ollama server is running and the "
                f"model '{self.model_name}' is installed. Details: {e}"
            ) from e

        # ChatResponse supports both dict-style and attribute access.
        if isinstance(response, dict):
            return response["message"]["content"]
        return response["message"]["content"]
