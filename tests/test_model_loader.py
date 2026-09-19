"""
Tests for core.model_loader.

Author: JAZZYLYFE
"""

import pytest


def _loader(model="dolphin-llama3"):
    from core.model_loader import ModelLoader

    return ModelLoader(model)


def test_config_loaded_and_default_model():
    ml = _loader(None)
    # default_model comes from config/model_config.yaml
    assert ml.model_name == "dolphin-llama3"
    assert isinstance(ml.config, dict)
    assert ml.config.get("default_model") == "dolphin-llama3"


def test_is_model_available_matches_modern_field(fake_ollama):
    """Regression: ollama >=0.4 exposes '.model', not 'name'.

    The old code read 'name' and always returned False.
    """
    fake_ollama.installed_models = ["dolphin-llama3:latest"]
    ml = _loader("dolphin-llama3")
    assert ml.is_model_available() is True


def test_is_model_available_false_when_absent(fake_ollama):
    fake_ollama.installed_models = ["some-other-model:latest"]
    ml = _loader("dolphin-llama3")
    assert ml.is_model_available() is False


def test_is_model_available_exact_tag_match(fake_ollama):
    fake_ollama.installed_models = ["deepseek-coder:6.7b"]
    ml = _loader("deepseek-coder:6.7b")
    assert ml.is_model_available() is True


def test_pull_model_skips_when_present(fake_ollama):
    fake_ollama.installed_models = ["dolphin-llama3:latest"]
    ml = _loader("dolphin-llama3")
    assert ml.pull_model() is True
    assert ml.client.pulled == []  # nothing downloaded


def test_pull_model_downloads_when_missing(fake_ollama):
    fake_ollama.installed_models = []
    ml = _loader("dolphin-llama3")
    assert ml.pull_model() is True
    assert "dolphin-llama3" in ml.client.pulled


def test_generate_forwards_system_prompt_and_options(fake_ollama):
    ml = _loader("dolphin-llama3")
    out = ml.generate("write code", system_prompt="SYSTEM RULES")
    assert "print('hi')" in out

    call = fake_ollama.last_call
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["system", "user"]
    assert call["messages"][0]["content"] == "SYSTEM RULES"
    # config forwards top_k and frequency_penalty
    assert call["options"]["top_k"] == 40
    assert call["options"]["frequency_penalty"] == 0.1
    assert "temperature" in call["options"]


def test_is_model_available_raises_when_server_down(fake_ollama):
    from core.model_loader import OllamaUnavailableError

    fake_ollama.raise_on_list = True
    ml = _loader("dolphin-llama3")
    with pytest.raises(OllamaUnavailableError):
        ml.is_model_available()


def test_generate_raises_when_server_down(fake_ollama):
    from core.model_loader import OllamaUnavailableError

    fake_ollama.raise_on_chat = True
    ml = _loader("dolphin-llama3")
    with pytest.raises(OllamaUnavailableError):
        ml.generate("write code")
