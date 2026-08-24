"""No literal control characters in source. This bug has shipped four times.

A `\b` written through a shell heredoc becomes a literal backspace (0x08).
The regex still compiles, the code still runs, the tests still pass -- and the
pattern can never match, so the feature is silently dead.

History in this repo:
  #145  guard_mock's raises-detection regex
  #170  the control-flow-exit suppressor
  #173  boundary injection targeting
  #174  _apply_guard_mock -- shipped inside the PR that was fixing #173's
        instance, and left rung 3's MagicMock branch unreachable

Every one passed CI. A grep is the only thing that catches this class, so it
lives in the suite rather than in a workflow step where it can be skipped.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import quell

PACKAGE_ROOT = Path(quell.__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent

# Control characters that must never appear literally in source. Tab, newline
# and carriage return are legitimate; these are not.
FORBIDDEN = {
    0x00: "NUL",
    0x07: "BEL (\a written through a heredoc)",
    0x08: "BACKSPACE (\b written through a heredoc)",
    0x0B: "VERTICAL TAB (\v)",
    0x0C: "FORM FEED (\f)",
    0x1B: r"ESCAPE (\e)",
}


def _python_sources() -> list[Path]:
    """Every file that can carry a hand-written regex.

    Originally .py only. That is exactly how the fifth occurrence got through:
    it landed in .github/workflows/ci.yml, in the commit correcting the record
    about the fourth. Workflow YAML embeds Python heredocs, so it is subject to
    the same escape-eating and must be scanned too.
    """
    roots = [
        PACKAGE_ROOT,
        PROJECT_ROOT / "benchmarks",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / ".github",
    ]
    patterns = ("*.py", "*.yml", "*.yaml")
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            files.extend(
                f for f in root.rglob(pattern)
                if ".venv" not in f.parts and "__pycache__" not in f.parts
            )
    return sorted(set(files))


@pytest.mark.parametrize("code,name", sorted(FORBIDDEN.items()))
def test_no_literal_control_characters(code: int, name: str):
    char = chr(code)
    offenders: list[str] = []

    for path in _python_sources():
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue
        if char not in text:
            continue
        # This file names the characters it forbids; skip its own table.
        if path.name == Path(__file__).name:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if char in line:
                rel = path.relative_to(PROJECT_ROOT)
                offenders.append(f"{rel}:{lineno}")

    assert not offenders, (
        f"literal {name} found at: {offenders}\n"
        "A regex escape was consumed by the shell. The pattern will never "
        "match and the feature is silently dead."
    )


def test_the_check_actually_looks_at_something():
    """A scan over zero files would pass vacuously forever."""
    files = _python_sources()
    assert len(files) > 50, f"only found {len(files)} source files to scan"
