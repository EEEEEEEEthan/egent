"""全项目 pylint 评分门禁。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_TARGETS = (
    str(PROJECT_ROOT / "examples" / "example_agent.py"),
    str(PROJECT_ROOT / "examples" / "example_workflow_coding.py"),
    str(PROJECT_ROOT / "examples" / "example_workflow_develop.py"),
    str(PROJECT_ROOT / "examples" / "example_workflow_review.py"),
    str(PROJECT_ROOT / "examples" / "example_workflow_todo.py"),
    str(PROJECT_ROOT / "examples" / "_common.py"),
    str(PROJECT_ROOT / "src" / "egent"),
)
TEST_TARGETS = (str(PROJECT_ROOT / "tests"),)
SCORE_PATTERN = re.compile(r"rated at ([\d.]+)/10")


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


def test_project_pylint_score_is_perfect() -> None:
    """examples、egent、tests 的 pylint 评分必须为 10/10。"""
    _assert_pylint_perfect(PRODUCTION_TARGETS)
    _assert_pylint_perfect(TEST_TARGETS, "--disable=duplicate-code")
