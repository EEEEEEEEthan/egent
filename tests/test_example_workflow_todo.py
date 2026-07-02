"""example_workflow_todo 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

# 将项目根目录和 examples 目录加入 sys.path，以便导入 examples 模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (str(PROJECT_ROOT), str(PROJECT_ROOT / "examples")):
    if path not in sys.path:
        sys.path.insert(0, path)


def _get_validator_cls() -> type:
    """延迟导入 TodoPathValidator，避免模块收集阶段的导入错误。"""
    # pylint: disable=import-error,import-outside-toplevel
    import examples.example_workflow_todo

    return examples.example_workflow_todo.TodoPathValidator


def test_todo_path_validator_blocks_edit_on_todo_file(tmp_path: Path) -> None:
    """TodoPathValidator 应阻止编辑 todo 文件本身。"""
    validator_cls = _get_validator_cls()
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    validator = validator_cls(todo_file)

    assert not validator.is_editable(todo_file)


def test_todo_path_validator_allows_edit_on_other_files_is_same_as_parent(
    tmp_path: Path,
) -> None:
    """TodoPathValidator 对非 todo 文件的编辑权限应与父类一致。"""
    validator_cls = _get_validator_cls()
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")

    validator = validator_cls(todo_file)

    # 任务清单文件本身不可编辑
    assert not validator.is_editable(todo_file)

    # 对于不存在的文件（不在 cwd 内），行为与父类一致
    nonexistent = tmp_path / "nonexistent.py"
    assert not validator.is_editable(nonexistent)


def test_todo_path_validator_inherits_parent_behavior(tmp_path: Path) -> None:
    """TodoPathValidator 对其他权限方法的处理应与父类一致。"""
    validator_cls = _get_validator_cls()
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    validator = validator_cls(todo_file)

    # tmp_path 不在 cwd 内，父类方法应返回 False
    assert not validator.is_discoverable(todo_file)
    assert not validator.is_readable(todo_file)
    assert not validator.is_searchable(todo_file)

    # 可编辑性：任务清单文件本身被阻止
    assert not validator.is_editable(todo_file)


def test_todo_path_validator_with_different_resolved_paths(tmp_path: Path) -> None:
    """TodoPathValidator 应正确处理路径解析（相同文件不同写法）。"""
    validator_cls = _get_validator_cls()
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    validator = validator_cls(todo_file)

    # 通过不同方式引用同一文件
    same_file_via_parent = todo_file.parent / "todo.txt"
    assert not validator.is_editable(same_file_via_parent)


def test_delegate_develop_workflow_tool_schema() -> None:
    """delegate_develop_workflow 应能生成合法的工具 schema。"""
    # pylint: disable=import-error,import-outside-toplevel
    import examples.example_workflow_develop
    from egent.tool import tool_from_function

    schema = tool_from_function(examples.example_workflow_develop.delegate_develop_workflow)
    function_schema = schema["function"]

    assert function_schema["name"] == "delegate_develop_workflow"
    assert "description" in function_schema["parameters"]["properties"]


def test_todo_path_validator_does_not_modify_other_permission_methods(
    tmp_path: Path,
) -> None:
    """TodoPathValidator 只重写 _is_editable，其他方法应保持父类行为。"""
    validator_cls = _get_validator_cls()
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    validator = validator_cls(todo_file)

    # 可读性、可发现性、可搜索性应保持父类行为
    # tmp_path 不在 cwd 内，故返回 False
    assert not validator.is_readable(todo_file)
    assert not validator.is_discoverable(todo_file)
    assert not validator.is_searchable(todo_file)
