"""Todo 列表逐条消化工作流。

运行::

    python examples/example_workflow_todo.py <todo文件路径>
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import _common
import example_workflow_develop
import egent.builtin_tools.path_validator


def create_todo_path_permissions(
    todo_path: Path,
) -> egent.builtin_tools.path_validator.PathPermissions:
    """todo 文件本身不可编辑，其余路径沿用默认权限。"""
    base = _common.create_egent_path_permissions()
    try:
        relative_todo = todo_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return base
    return dataclasses.replace(
        base,
        editable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=base.editable.whitelist,
            blacklist=base.editable.blacklist + (relative_todo,),
        ),
    )


def _read_first_task(content: str) -> str:
    """从文本中提取第一行非空内容作为任务描述，无任务时返回空字符串。"""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _remove_first_task(content: str) -> str:
    """删除文本中第一行非空行，返回剩余内容。"""
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    skipped = False
    for line in lines:
        if not skipped and line.strip():
            skipped = True
            continue
        new_lines.append(line)
    return "".join(new_lines)


def _git_commit(message: str) -> None:
    """暂存全部变更并提交。"""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=Path.cwd(),
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=Path.cwd(),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ git 操作失败 (可能无需提交): {exc.stderr.strip()}")


def _print_result_summary(results: list[tuple[str, bool, str]]) -> str:
    """打印全部结果汇总并返回汇总字符串。"""
    print("\n" + "=" * 60)
    print("📊 全部任务完成汇总")
    print("=" * 60)
    for idx, (task, success, summary) in enumerate(results, start=1):
        status = "✅" if success else "❌"
        print(f"\n{idx}. {status} {task}")
        first_lines = summary.strip().split("\n")[:2]
        for line in first_lines:
            print(f"   {line}")

    result_lines = ["# Todo 消化工作流完成\n"]
    result_lines.append(f"共处理 {len(results)} 条任务:\n")
    for idx, (task, success, _) in enumerate(results, start=1):
        status = "✅" if success else "❌"
        result_lines.append(f"{idx}. {status} {task}")
    return "\n".join(result_lines)


async def todo_digest_workflow(todo_file: str) -> str:
    """逐条开发 todo 文件中的任务列表。
    直至 todo 文件为空，或某条任务失败时立即结束。

    @param todo_file: todo 文件路径
    """
    todo_path = Path(todo_file).resolve()
    if not todo_path.exists():
        return f"错误: 文件不存在: {todo_path}"

    todo_permissions = create_todo_path_permissions(todo_path)
    results: list[tuple[str, bool, str]] = []

    while True:
        content = todo_path.read_text(encoding="utf-8")
        first_line = _read_first_task(content)
        if not first_line:
            break

        print("=" * 60)
        print(f"📋 任务: {first_line}")
        print("=" * 60)

        try:
            success, summary = await example_workflow_develop.begin_develop_workflow(
                first_line, custom_path_permissions=todo_permissions
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            success = False
            summary = f"❌ 开发过程异常: {exc}"
            print(summary)

        results.append((first_line, success, summary))
        if not success:
            return _print_result_summary(results)

        new_content = _remove_first_task(content)
        todo_path.write_text(new_content, encoding="utf-8")
        _git_commit(f"✅ {first_line}")

    return _print_result_summary(results)


async def async_main() -> int:
    """入口函数。"""
    if len(sys.argv) < 2:
        print("用法: python example_workflow_todo.py <todo文件路径>")
        return 1
    todo_file = sys.argv[1]
    result = await todo_digest_workflow(todo_file)
    print(f"\n{result}")
    return 0


if __name__ == "__main__":
    _common.run_cli(async_main)
