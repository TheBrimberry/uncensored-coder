"""
Tests for core.code_generator.

Author: JAZZYLYFE
"""

import os


def _gen(model="dolphin-llama3"):
    from core.code_generator import CodeGenerator

    return CodeGenerator(model=model, enable_logging=False)


def test_clean_code_strips_fences():
    g = _gen()
    fenced = "Here you go:\n```python\nprint('x')\n```\nThanks!"
    assert g._clean_code(fenced) == "print('x')"


def test_clean_code_passthrough_without_fences():
    g = _gen()
    assert g._clean_code("  raw code  ") == "raw code"


def test_generate_returns_clean_code(fake_ollama):
    fake_ollama.chat_reply = "```python\nx = 1\nprint(x)\n```"
    g = _gen()
    out = g.generate("make a var", "python")
    assert out == "x = 1\nprint(x)"


def test_generate_sends_system_prompt(fake_ollama):
    g = _gen()
    g.generate("do a thing", "rust")
    msgs = fake_ollama.last_call["messages"]
    assert msgs[0]["role"] == "system"
    assert "RAW_CODE_GENERATOR" in msgs[0]["content"]
    assert "rust" in msgs[0]["content"].lower()


def test_ensure_ready_pulls_when_missing(fake_ollama):
    fake_ollama.installed_models = []
    g = _gen()
    assert g.ensure_ready() is True
    assert "dolphin-llama3" in g.loader.client.pulled


def test_save_to_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = _gen()
    path = g.save_to_file("print('saved')", "out.py")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        assert f.read() == "print('saved')"
