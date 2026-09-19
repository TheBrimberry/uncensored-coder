"""
Tests for interface.cli helpers.

Author: JAZZYLYFE
"""

import pytest


@pytest.fixture
def cli():
    from interface.cli import CLI

    class DummyGen:
        def generate(self, *a, **k):
            return "code"

        def save_to_file(self, code, filename):
            return f"generated_code/{filename}"

    return CLI(DummyGen())


@pytest.mark.parametrize(
    "text,expected",
    [
        ("write a javascript function", "javascript"),
        ("write a java class", "java"),
        ("build a website in html", "html"),
        ("make a typescript module", "typescript"),
        ("just do something", "python"),
        ("a rust cli", "rust"),
    ],
)
def test_detect_language(cli, text, expected):
    assert cli._detect_language(text) == expected


def test_javascript_not_clobbered_by_java(cli):
    # Regression: substring "java" must not override "javascript".
    assert cli._detect_language("javascript app") == "javascript"


def test_lang_extensions_cover_supported_languages():
    from interface.cli import LANG_EXTENSIONS

    assert LANG_EXTENSIONS["python"] == "py"
    assert LANG_EXTENSIONS["javascript"] == "js"
    assert LANG_EXTENSIONS["rust"] == "rs"
