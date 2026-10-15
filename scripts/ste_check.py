"""Find style problems in comments, docstrings, and Markdown prose."""
from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKED_SUFFIXES = {".scala", ".py", ".sh", ".md"}
SKIPPED_NAMES = {
    "docs/BUILD_PLAN.md",
    "AGENTS.md",
    "scripts/ste_check.py",
    "python/tests/test_ste_check.py",
}
SKIPPED_DIRECTORIES = {
    ".git", ".venv", "target", "data", "logs", "__pycache__", ".pytest_cache",
    "spark-warehouse", "metastore_db",
}
MAX_SENTENCE_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 6

NOT_ALLOWED_WORDS = [
    "delve", "robust", "seamless", "seamlessly", "leverage", "comprehensive",
    "cutting-edge", "state-of-the-art", "game-changer", "powerful", "powerfully",
    "streamline", "crucial", "pivotal", "holistic", "unlock", "harness", "tapestry",
    "landscape", "elevate", "empower", "journey", "synergy", "paradigm",
    "it is worth noting", "it is important to note", "in today's world", "let's",
    "dive into", "moreover", "furthermore", "additionally", "overall",
    "in conclusion", "in summary", "basically", "essentially", "simply", "just",
    "very", "really", "quite",
    "utilize", "perform", "ensure", "in order to", "prior to", "subsequent",
    "subsequently", "approximately", "additional", "terminate", "obtain",
    "commence", "require", "requires",
]
WORD_PATTERNS = [
    (word, re.compile(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", re.IGNORECASE))
    for word in NOT_ALLOWED_WORDS
]
CONTRACTION = re.compile(
    r"\b\w+n['’]t\b|\b\w+['’](?:re|ve|ll|m|d)\b|\b(?:it|that|there|what|here)['’]s\b",
    re.IGNORECASE,
)
ABBREVIATION = re.compile(r"\b(?:e\.g\.|i\.e\.)", re.IGNORECASE)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F]")
EM_DASH = "\u2014"
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def split_sentences(text: str) -> list[str]:
    """Split a text block into sentences."""
    return [part.strip() for part in SENTENCE_BREAK.split(text.strip()) if part.strip()]


def word_count(sentence: str) -> int:
    """Count the words in one sentence."""
    return len(re.findall(r"[A-Za-z0-9][\w'’./-]*", sentence))


def check_block(text: str, is_paragraph: bool) -> list[str]:
    """Return the problem descriptions for one block of prose."""
    problems: list[str] = []
    sentences = split_sentences(text)
    for sentence in sentences:
        count = word_count(sentence)
        if count > MAX_SENTENCE_WORDS:
            problems.append(f"sentence has {count} words (maximum {MAX_SENTENCE_WORDS})")
    if is_paragraph and len(sentences) > MAX_PARAGRAPH_SENTENCES:
        problems.append(
            f"paragraph has {len(sentences)} sentences (maximum {MAX_PARAGRAPH_SENTENCES})"
        )
    for word, pattern in WORD_PATTERNS:
        if pattern.search(text):
            problems.append(f"word or phrase not allowed: '{word}'")
    if CONTRACTION.search(text):
        problems.append("contraction found")
    if "!" in text:
        problems.append("exclamation mark found")
    if EM_DASH in text:
        problems.append("em dash found")
    if EMOJI.search(text):
        problems.append("emoji found")
    if ABBREVIATION.search(text):
        problems.append("abbreviation e.g. or i.e. found")
    return problems


def group_comment_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Join comment lines on adjacent line numbers into one block."""
    blocks: list[tuple[int, str]] = []
    previous = -2
    for number, text in lines:
        if number == previous + 1 and blocks:
            start, joined = blocks[-1]
            blocks[-1] = (start, f"{joined} {text}")
        else:
            blocks.append((number, text))
        previous = number
    return blocks


def python_blocks(source: str) -> list[tuple[int, str, bool]]:
    """Return (line, text, is_paragraph) for comments and docstrings."""
    comment_lines = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comment_lines.append((token.start[0], token.string.lstrip("#").strip()))
    blocks = [(n, t, True) for n, t in group_comment_lines(comment_lines)]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            text = ast.get_docstring(node, clean=True)
            if text and node.body:
                blocks.append((node.body[0].lineno, " ".join(text.split()), True))
    return blocks


def slash_blocks(source: str) -> list[tuple[int, str, bool]]:
    """Return (line, text, is_paragraph) for Scala line and block comments."""
    comment_lines = []
    for number, line in enumerate(source.splitlines(), start=1):
        match = re.search(r"(?:^|\s)//\s?(.*)$", line)
        if match:
            comment_lines.append((number, match.group(1).strip()))
    blocks = [(n, t, True) for n, t in group_comment_lines(comment_lines)]
    for match in re.finditer(r"/\*(.*?)\*/", source, re.DOTALL):
        number = source.count("\n", 0, match.start()) + 1
        text = " ".join(re.sub(r"^\s*\*+\s?", "", row) for row in match.group(1).splitlines())
        blocks.append((number, " ".join(text.split()), True))
    return blocks


def shell_blocks(source: str) -> list[tuple[int, str, bool]]:
    """Return (line, text, is_paragraph) for shell comment lines."""
    comment_lines = []
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            comment_lines.append((number, stripped.lstrip("#").strip()))
    return [(n, t, True) for n, t in group_comment_lines(comment_lines)]


def clean_markdown(text: str) -> str:
    """Remove inline code, links, and emphasis marks from Markdown text."""
    text = re.sub(r"`[^`]*`", "code", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.replace("**", "").replace("__", "").replace("\\_", "_")


def markdown_blocks(source: str) -> list[tuple[int, str, bool]]:
    """Return (line, text, is_paragraph) for prose, skipping code blocks and tables."""
    blocks: list[tuple[int, str, bool]] = []
    paragraph: list[tuple[int, str]] = []
    in_fence = False

    def flush() -> None:
        if paragraph:
            joined = " ".join(text for _, text in paragraph)
            blocks.append((paragraph[0][0], clean_markdown(joined), True))
            paragraph.clear()

    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
        elif in_fence or stripped.startswith("|"):
            flush()
        elif not stripped:
            flush()
        elif stripped.startswith("#") or LIST_ITEM.match(line):
            flush()
            blocks.append((number, clean_markdown(LIST_ITEM.sub("", stripped)), False))
        else:
            paragraph.append((number, stripped))
    flush()
    return blocks


def check_source(suffix: str, source: str) -> list[tuple[int, str]]:
    """Return (line, problem) pairs for the source text of one file type."""
    extractors = {
        ".py": python_blocks, ".scala": slash_blocks, ".sh": shell_blocks,
        ".md": markdown_blocks,
    }
    results: list[tuple[int, str]] = []
    for number, text, is_paragraph in extractors[suffix](source):
        for problem in check_block(text, is_paragraph):
            results.append((number, problem))
    return sorted(results)


def check_file(path: Path) -> list[str]:
    """Return the problem lines for one file, prefixed with name and line."""
    source = path.read_text(encoding="utf-8")
    return [f"{path}:{n}: {p}" for n, p in check_source(path.suffix, source)]


def find_files(root: Path) -> list[Path]:
    """Find the files that the style check reads."""
    found = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.suffix not in CHECKED_SUFFIXES:
            continue
        if SKIPPED_DIRECTORIES & set(relative.parts):
            continue
        if relative.as_posix() in SKIPPED_NAMES:
            continue
        found.append(relative)
    return found


def main(argv: list[str]) -> int:
    """Run the style check on the repository and return the exit code."""
    root = Path(argv[0]).resolve() if argv else ROOT
    problems: list[str] = []
    for relative in find_files(root):
        problems.extend(check_file(relative if root == Path.cwd() else root / relative))
    if problems:
        print("\n".join(problems))
        print(f"STE CHECK FAILED: {len(problems)} problems")
        return 1
    print("STE CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
