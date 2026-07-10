"""技能 learn_skill / run_skill_script 内置工具。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import egent.builtin_tools.command_utils
import egent.tool

__all__ = ["get_skill_tools"]


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

    def learn_skill(skill_id: str) -> str:
        """读取技能目录结构与 SKILL.md 全文。

        @param skill_id 技能 id
        """
        skill_dir = require_skill_dir(skill_id)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise FileNotFoundError(f"技能目录缺少 SKILL.md：{skill_dir}")
        tree_lines = [f"{skill_dir.name}/"]
        for path in sorted(skill_dir.rglob("*")):
            relative = path.relative_to(skill_dir)
            indent = "  " * len(relative.parts)
            suffix = "/" if path.is_dir() else ""
            tree_lines.append(f"{indent}{relative.as_posix()}{suffix}")
        return (
            f"# 技能目录: {skill_id}\n\n"
            f"{'\n'.join(tree_lines)}\n\n"
            f"# SKILL.md\n\n"
            f"{skill_md.read_text(encoding='utf-8')}"
        )

    def resolve_script(skill_dir: Path, script_relative_path: str) -> Path:
        relative = Path(script_relative_path)
        if relative.is_absolute():
            raise ValueError(f"脚本路径必须为相对路径：{script_relative_path}")
        resolved_skill_dir = skill_dir.resolve()
        script_path = (resolved_skill_dir / relative).resolve()
        try:
            script_path.relative_to(resolved_skill_dir)
        except ValueError as path_error:
            raise ValueError(f"脚本路径越界：{script_relative_path}") from path_error
        if not script_path.is_file():
            raise FileNotFoundError(f"脚本不存在：{script_relative_path}")
        return script_path

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
        script_path = resolve_script(skill_dir, script_relative_path)
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
