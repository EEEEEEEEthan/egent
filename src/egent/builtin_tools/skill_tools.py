"""技能 learn_skill / run_skill_script 内置工具。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import egent.builtin_tools.command_utils
import egent.tool

__all__ = ["get_skill_tools"]

_SKILL_ENTRY_NAME = "SKILL.md"


def get_skill_tools(skill_index: dict[str, Path]) -> list[egent.tool.ToolCallable]:
    """返回绑定到给定技能索引的工具函数列表。"""

    def require_skill_dir(skill_id: str) -> Path:
        skill_dir = skill_index.get(skill_id)
        if skill_dir is None:
            known = ", ".join(sorted(skill_index)) or "（无）"
            raise ValueError(f"未知技能 id：{skill_id}，已知：{known}")
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"技能目录不存在：{skill_dir}")
        return skill_dir

    def resolve_under_skill(skill_dir: Path, relative_path: str) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute():
            raise ValueError(f"路径必须为相对路径：{relative_path}")
        resolved_skill_dir = skill_dir.resolve()
        target_path = (resolved_skill_dir / relative).resolve()
        try:
            target_path.relative_to(resolved_skill_dir)
        except ValueError as path_error:
            raise ValueError(f"路径越界：{relative_path}") from path_error
        return target_path

    def learn_skill(skill_id: str, relative_path: str = _SKILL_ENTRY_NAME) -> str:
        """读取技能目录下的文件；缺省为 SKILL.md（附目录树）。

        @param skill_id 技能 id
        @param relative_path 相对技能目录的文件路径，默认 SKILL.md
        """
        skill_dir = require_skill_dir(skill_id)
        file_path = resolve_under_skill(skill_dir, relative_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"文件不存在：{relative_path}")
        content = file_path.read_text(encoding="utf-8")
        display_path = Path(relative_path).as_posix()
        skill_entry = skill_dir.resolve() / _SKILL_ENTRY_NAME
        if file_path != skill_entry:
            return f"# 技能文件: {skill_id}/{display_path}\n\n{content}"
        tree_lines = [f"{skill_dir.name}/"]
        for path in sorted(skill_dir.rglob("*")):
            relative = path.relative_to(skill_dir)
            indent = "  " * len(relative.parts)
            suffix = "/" if path.is_dir() else ""
            tree_lines.append(f"{indent}{relative.as_posix()}{suffix}")
        return (
            f"# 技能目录: {skill_id}\n\n"
            f"{'\n'.join(tree_lines)}\n\n"
            f"# {_SKILL_ENTRY_NAME}\n\n"
            f"{content}"
        )

    def run_skill_script(
        skill_id: str,
        script_relative_path: str,
        args: list[str] | None = None,
    ) -> str:
        """运行技能目录下的脚本。

        @param skill_id 技能 id
        @param script_relative_path 相对技能目录的脚本路径
        @param args 传给脚本的命令行参数
        """
        skill_dir = require_skill_dir(skill_id)
        script_path = resolve_under_skill(skill_dir, script_relative_path)
        if not script_path.is_file():
            raise FileNotFoundError(f"脚本不存在：{script_relative_path}")
        suffix = script_path.suffix.lower()
        if suffix == ".py":
            command = [sys.executable, str(script_path), *(args or [])]
        elif suffix == ".ps1":
            command = ["powershell", "-NoProfile", "-File", str(script_path), *(args or [])]
        elif suffix in {".sh", ".bash"}:
            command = ["bash", str(script_path), *(args or [])]
        elif suffix in {".bat", ".cmd"}:
            command = [str(script_path), *(args or [])]
        else:
            raise ValueError(f"不支持的脚本类型：{script_path.suffix}")
        completed = subprocess.run(
            command,
            cwd=script_path.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return egent.builtin_tools.command_utils.format_command_result(
            completed.stdout, completed.stderr, completed.returncode
        )

    return [learn_skill, run_skill_script]
