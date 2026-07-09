"""example_workflow_todo 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

# 将项目根目录和 examples 目录加入 sys.path，以便导入 examples 模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (str(PROJECT_ROOT), str(PROJECT_ROOT / "examples")):
    if path not in sys.path:
        sys.path.insert(0, path)


def _create_todo_permissions(todo_file: Path):
    """延迟导入 create_todo_path_permissions，避免模块收集阶段的导入错误。"""
    # pylint: disable=import-error,import-outside-toplevel
    import examples.example_workflow_todo

    return examples.example_workflow_todo.create_todo_path_permissions(todo_file)


def test_todo_path_permissions_blocks_edit_on_todo_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """todo 权限应阻止编辑 todo 文件本身。"""
    monkeypatch.chdir(tmp_path)
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    permissions = _create_todo_permissions(todo_file)

    assert not permissions.is_editable(todo_file)


def test_todo_path_permissions_allows_edit_on_other_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """todo 权限对非 todo 文件的编辑行为应与默认权限一致。"""
    monkeypatch.chdir(tmp_path)
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    other_file = tmp_path / "notes.txt"
    permissions = _create_todo_permissions(todo_file)

    assert not permissions.is_editable(todo_file)
    assert permissions.is_editable(other_file)


def test_todo_path_permissions_inherits_default_behavior(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """todo 权限对其他权限项的处理应与默认权限一致。"""
    monkeypatch.chdir(tmp_path)
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    permissions = _create_todo_permissions(todo_file)

    assert permissions.is_discoverable(todo_file)
    assert permissions.is_readable(todo_file)
    assert permissions.is_searchable(todo_file)
    assert not permissions.is_editable(todo_file)


def test_todo_path_permissions_with_different_resolved_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """todo 权限应正确处理路径解析（相同文件不同写法）。"""
    monkeypatch.chdir(tmp_path)
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    permissions = _create_todo_permissions(todo_file)

    same_file_via_parent = todo_file.parent / "todo.txt"
    assert not permissions.is_editable(same_file_via_parent)


def test_todo_path_permissions_outside_cwd_has_no_access(tmp_path: Path) -> None:
    """cwd 外的路径应无任何权限。"""
    todo_file = tmp_path / "todo.txt"
    todo_file.write_text("task 1\n", encoding="utf-8")
    permissions = _create_todo_permissions(todo_file)

    assert not permissions.is_discoverable(todo_file)
    assert not permissions.is_readable(todo_file)
    assert not permissions.is_editable(todo_file)
    assert not permissions.is_searchable(todo_file)


def test_delegate_develop_workflow_tool_schema() -> None:
    """delegate_develop_workflow 应能生成合法的工具 schema。"""
    # pylint: disable=import-error,import-outside-toplevel
    import examples.example_workflow_develop
    from egent.tool import tool_from_function

    schema = tool_from_function(examples.example_workflow_develop.delegate_develop_workflow)
    function_schema = schema["function"]

    assert function_schema["name"] == "delegate_develop_workflow"
    assert "description" in function_schema["parameters"]["properties"]
