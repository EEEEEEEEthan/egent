"""example_workflow_develop 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (str(PROJECT_ROOT), str(PROJECT_ROOT / "examples")):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_delegate_develop_workflow_tool_schema() -> None:
    """delegate_develop_workflow 应能生成合法的工具 schema。"""
    # pylint: disable=import-error,import-outside-toplevel
    import examples.example_workflow_develop
    from egent.tool import tool_from_function

    schema = tool_from_function(examples.example_workflow_develop.delegate_develop_workflow)
    function_schema = schema["function"]

    assert function_schema["name"] == "delegate_develop_workflow"
    assert "description" in function_schema["parameters"]["properties"]
