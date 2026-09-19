"""
Shared test fixtures.

Installs a lightweight fake ``ollama`` module before the project imports it,
so the whole suite runs fully offline with no server and no real dependency.

Author: JAZZYLYFE
"""

import os
import sys
import types

import pytest

# Make the project root importable (tests/ -> repo root).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class FakeModelEntry:
    """Mimics ollama >=0.4 ListResponse.Model (field is ``model``, not ``name``)."""

    def __init__(self, model):
        self.model = model

    def get(self, key, default=None):
        return getattr(self, key, default)


class FakeListResponse:
    def __init__(self, models):
        self.models = [FakeModelEntry(m) for m in models]


class FakeChatMessage(dict):
    """Subscriptable like ollama's ChatResponse.message."""


class FakeClient:
    """A configurable stand-in for ollama.Client."""

    installed_models = ["dolphin-llama3:latest"]
    raise_on_list = False
    raise_on_chat = False
    chat_reply = "```python\nprint('hi')\n```"

    def __init__(self, *args, **kwargs):
        self.pulled = []

    def list(self):
        if type(self).raise_on_list:
            raise ConnectionError("connection refused")
        return FakeListResponse(list(type(self).installed_models))

    def pull(self, name):
        self.pulled.append(name)
        type(self).installed_models = list(type(self).installed_models) + [name]
        return {"status": "success"}

    def chat(self, model, messages, options=None):
        if type(self).raise_on_chat:
            raise ConnectionError("connection refused")
        # capture what was sent for assertions
        type(self).last_call = {"model": model, "messages": messages, "options": options}
        return {"message": {"content": type(self).chat_reply}}


@pytest.fixture(autouse=True)
def fake_ollama(monkeypatch):
    """Provide a fake ``ollama`` module for every test and reset its state."""
    module = types.ModuleType("ollama")
    module.Client = FakeClient
    monkeypatch.setitem(sys.modules, "ollama", module)

    # Reset class-level state between tests.
    FakeClient.installed_models = ["dolphin-llama3:latest"]
    FakeClient.raise_on_list = False
    FakeClient.raise_on_chat = False
    FakeClient.chat_reply = "```python\nprint('hi')\n```"

    # Ensure modules that imported ollama at import-time pick up the fake.
    for mod in ("core.model_loader", "core.code_generator"):
        sys.modules.pop(mod, None)

    yield FakeClient
