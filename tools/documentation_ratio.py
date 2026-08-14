"""Measure internal documentation in Athena production Python sources.

The metric counts physical non-empty lines. A documentation line is either a
full-line ``#`` comment or a line belonging to a module/class/function docstring.
Generated data, tooling and scratch scripts are excluded from the application
scope.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("collectors", "models", "repositories", "services", "ui", "utils")
ROOT_FILES = ("main.py",)
DOCSTRING_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def source_files() -> list[Path]:
    files = [ROOT / name for name in ROOT_FILES]
    for directory in SOURCE_ROOTS:
        files.extend(sorted((ROOT / directory).rglob("*.py")))
    return [path for path in files if path.is_file()]


def docstring_line_numbers(source: str) -> set[int]:
    lines: set[int] = set()
    tree = ast.parse(source)
    for node in [tree, *ast.walk(tree)]:
        if not isinstance(node, DOCSTRING_NODES) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            start = first.lineno
            end = getattr(first, "end_lineno", start)
            lines.update(range(start, end + 1))
    return lines


def comment_line_numbers(source: str) -> set[int]:
    lines: set[int] = set()
    physical = source.splitlines()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        prefix = physical[token.start[0] - 1][: token.start[1]]
        if not prefix.strip():
            lines.add(token.start[0])
    return lines


def measure(path: Path) -> tuple[int, int]:
    source = path.read_text(encoding="utf-8")
    physical = source.splitlines()
    non_empty = {index for index, line in enumerate(physical, start=1) if line.strip()}
    documentation = (docstring_line_numbers(source) | comment_line_numbers(source)) & non_empty
    return len(non_empty), len(documentation)


def main() -> None:
    total_non_empty = 0
    total_documentation = 0
    print("Athena internal documentation ratio")
    print("scope: main.py + collectors/models/repositories/services/ui/utils")
    print()

    for path in source_files():
        non_empty, documentation = measure(path)
        total_non_empty += non_empty
        total_documentation += documentation
        ratio = (documentation / non_empty * 100) if non_empty else 0.0
        print(f"{path.relative_to(ROOT)!s:48} {documentation:4}/{non_empty:4}  {ratio:6.2f}%")

    ratio = total_documentation / total_non_empty * 100 if total_non_empty else 0.0
    print()
    print(f"TOTAL_DOCUMENTATION_LINES={total_documentation}")
    print(f"TOTAL_NON_EMPTY_LINES={total_non_empty}")
    print(f"DOCUMENTATION_RATIO={ratio:.2f}%")


if __name__ == "__main__":
    main()
