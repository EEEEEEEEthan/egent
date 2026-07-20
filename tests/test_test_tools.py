"""test_tools 单元测试。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import egent.builtin_tools.test_tools
import egent.tool


def test_execute_pytest_runs_full_suite(monkeypatch) -> None:
    """无 targets 时应跑全量 pytest。"""
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(egent.builtin_tools.test_tools.subprocess, "run", fake_run)

    passed, output = egent.builtin_tools.test_tools.execute_pytest(None)

    assert passed is True
    assert captured["command"] == [
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "auto",
        "--dist",
        "load",
    ]
    assert captured["kwargs"]["cwd"] == Path.cwd()
    assert "exit_code: 0" in output


def test_execute_pytest_passes_targets(monkeypatch) -> None:
    """应把 targets 传给 pytest。"""
    captured: dict[str, object] = {}

    def fake_run(command, **_kwargs):  # type: ignore[no-untyped-def]
        captured["command"] = command
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="fail\n")

    monkeypatch.setattr(egent.builtin_tools.test_tools.subprocess, "run", fake_run)

    passed, output = egent.builtin_tools.test_tools.execute_pytest(
        ["tests/test_foo.py::test_bar"],
    )

    assert passed is False
    assert captured["command"] == [
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "auto",
        "--dist",
        "load",
        "tests/test_foo.py::test_bar",
    ]
    assert "fail" in output
    assert "exit_code: 1" in output


def test_run_regression_test_reports_success(monkeypatch) -> None:
    """工具应返回通过信息。"""
    monkeypatch.setattr(
        egent.builtin_tools.test_tools,
        "execute_pytest",
        lambda targets: (True, "exit_code: 0"),
    )

    result = egent.builtin_tools.test_tools.run_regression_test("tests/test_foo.py")

    assert result == "回归测试通过（tests/test_foo.py）"


def test_run_regression_test_reports_failure(monkeypatch) -> None:
    """工具应返回失败详情。"""
    monkeypatch.setattr(
        egent.builtin_tools.test_tools,
        "execute_pytest",
        lambda targets: (False, "FAILED\nexit_code: 1"),
    )

    result = egent.builtin_tools.test_tools.run_regression_test("")

    assert result == "全量回归测试未通过：\nFAILED\nexit_code: 1"


def test_run_regression_test_tool_schema() -> None:
    """run_regression_test 应能生成合法工具 schema。"""
    schema = egent.tool.tool_from_function(egent.builtin_tools.test_tools.run_regression_test)
    function_schema = schema["function"]

    assert function_schema["name"] == "run_regression_test"
    assert "targets" in function_schema["parameters"]["properties"]
