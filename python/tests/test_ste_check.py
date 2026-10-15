"""Tests for the style check script."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import ste_check  # noqa: E402


def problems(suffix: str, source: str) -> list[str]:
    """Return only the problem texts for a fixture source."""
    return [text for _, text in ste_check.check_source(suffix, source)]


def test_clean_comment_passes() -> None:
    """Check that a short plain comment has no problem."""
    assert problems(".py", "# Read the file.\nx = 1\n") == []


def test_long_sentence_is_reported() -> None:
    """Check that a sentence of 26 words is reported."""
    sentence = " ".join(["word"] * 26) + "."
    assert any("26 words" in text for text in problems(".sh", f"# {sentence}\n"))


def test_long_paragraph_is_reported() -> None:
    """Check that a paragraph of 7 sentences is reported."""
    text = " ".join(["Run the check."] * 7)
    assert any("7 sentences" in item for item in problems(".md", text + "\n"))


def test_not_allowed_word_is_reported() -> None:
    """Check that a word from the not allowed list is reported."""
    assert any("robust" in text for text in problems(".py", "# A robust step.\n"))


def test_word_inside_longer_word_is_accepted() -> None:
    """Check that a longer word that contains a listed word passes."""
    assert problems(".py", "# Check the performance.\n") == []


def test_contraction_exclamation_and_dash_are_reported() -> None:
    """Check the character level rules."""
    assert "contraction found" in problems(".py", "# It doesn't run.\n")
    assert "exclamation mark found" in problems(".py", "# Stop!\n")
    assert "em dash found" in problems(".py", "# One \u2014 two.\n")
    assert "abbreviation e.g. or i.e. found" in problems(".scala", "// e.g. a row\n")


def test_markdown_skips_code_blocks_and_tables() -> None:
    """Check that Markdown code blocks and tables are not read."""
    source = "```\nThis is a robust example!\n```\n\n| robust | very |\n"
    assert problems(".md", source) == []


def test_scala_block_comment_is_read() -> None:
    """Check that a Scala block comment is read."""
    assert any("just" in t for t in problems(".scala", "/* Do it just now. */\n"))
