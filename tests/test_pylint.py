"""全项目 pylint 评分与导入风格门禁。"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_TARGETS = (
    str(PROJECT_ROOT / "examples" / "example_agent.py"),
    str(PROJECT_ROOT / "src" / "egent"),
)
TEST_TARGETS = (str(PROJECT_ROOT / "tests"),)
SCORE_PATTERN = re.compile(r"rated at ([\d.]+)/10")
_SCAN_ROOTS = (
    PROJECT_ROOT / "examples",
    PROJECT_ROOT / "src" / "egent",
    PROJECT_ROOT / "tests",
)


def _assert_pylint_perfect(targets: tuple[str, ...], *extra_args: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pylint", *extra_args, *targets],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = SCORE_PATTERN.search(output)
    assert match is not None, output
    score = float(match.group(1))
    assert score == 10.0, output
    assert completed.returncode == 0, output


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        files.extend(sorted(root.rglob("*.py")))
    return files


def _is_project_from_import(node: ast.ImportFrom) -> bool:
    if node.level and node.level > 0:
        return True
    module = node.module or ""
    return module == "egent" or module.startswith("egent.")


def test_project_pylint_score_is_perfect() -> None:
    """examples、egent、tests 的 pylint 评分必须为 10/10。"""
    _assert_pylint_perfect(PRODUCTION_TARGETS)
    _assert_pylint_perfect(TEST_TARGETS, "--disable=duplicate-code")


def test_no_project_from_imports() -> None:
    """禁止对本项目模块使用 from-import（含相对导入）。"""
    violations: list[str] = []
    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not _is_project_from_import(node):
                continue
            module = node.module or ""
            relative = "." * node.level
            display = f"{relative}{module}" if module else relative
            violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: from {display} import ...")
    assert not violations, "发现本项目 from-import:\n" + "\n".join(violations)
