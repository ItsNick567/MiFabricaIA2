"""Tests for tutorial generation flow."""

from unittest.mock import patch

from core.content_generator import TutorialGenerator


def _sample_tutorial_text() -> str:
    return (
        "## Introduction\n"
        "You will learn Git step by step.\n\n"
        "## Step 1\n"
        "Run:\n"
        "```bash\n"
        "git init\n"
        "```\n\n"
        "## Conclusion\n"
        "Done.\n"
    )


def test_generation_with_groq() -> None:
    """Ensure Groq generation path returns structured payload."""
    generator = TutorialGenerator()
    with patch("core.content_generator.generar_texto_motor", return_value=_sample_tutorial_text()):
        result = generator.generate_tutorial("Test topic", engine="Groq")

    assert result is not None
    assert len(result["sections"]) > 0
    assert result["llm_used"] == "groq"
    assert result["quality"]["language"] == "en"


def test_fallback_to_ollama() -> None:
    """Ensure fallback path reaches second engine when first fails."""
    generator = TutorialGenerator()
    with patch("core.content_generator.generar_texto_motor", side_effect=[None, _sample_tutorial_text(), None]):
        result = generator.generate_tutorial("Fallback topic")

    assert result is not None
    assert result["llm_used"] in ["ollama", "gemini"]
    assert result["quality"]["language"] == "en"
