"""技能工具单元测试。"""

# pylint: disable=protected-access

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import egent.builtin_tools.skill_tools
import egent.agent
import egent.tool


def _write_skill(skill_dir, name: str, description: str, extra: str = "") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# Body\n{extra}",
        encoding="utf-8",
    )


def test_build_skills_deduplicates_ids(tmp_path) -> None:
    """重名技能应自动追加 _2 后缀。"""
    first = tmp_path / "alpha"
    second = tmp_path / "beta"
    _write_skill(first, "demo", "第一个")
    _write_skill(second, "demo", "第二个")

    index, _catalog = egent.agent.Agent._Agent__build_skills([first, second])

    assert set(index) == {"demo", "demo_2"}
    assert index["demo"] == first.resolve()
    assert index["demo_2"] == second.resolve()


def test_build_skills_catalog_includes_descriptions(tmp_path) -> None:
    """技能摘要应包含 id 与 description。"""
    skill_dir = tmp_path / "git-commit"
    _write_skill(skill_dir, "git-commit", "执行提交")

    _index, catalog = egent.agent.Agent._Agent__build_skills([skill_dir])

    assert "git-commit: 执行提交" in catalog


def test_learn_skill_outputs_tree_and_skill_md(tmp_path) -> None:
    """learn_skill 缺省应先输出目录结构再输出 SKILL.md。"""
    skill_dir = tmp_path / "demo"
    _write_skill(skill_dir, "demo", "演示技能", extra="正文")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")

    learn_skill, _ = egent.builtin_tools.skill_tools.get_skill_tools(egent.agent.Agent._Agent__build_skills([skill_dir])[0])
    result = learn_skill("demo")

    tree_index = result.index("demo/")
    skill_md_index = result.index("# SKILL.md")
    assert tree_index < skill_md_index
    assert "scripts/run.py" in result
    assert "演示技能" in result
    assert "正文" in result


def test_learn_skill_reads_relative_file(tmp_path) -> None:
    """learn_skill 指定相对路径时应只返回该文件内容。"""
    skill_dir = tmp_path / "demo"
    _write_skill(skill_dir, "demo", "演示技能")
    rules = skill_dir / "rules"
    rules.mkdir()
    (rules / "detail.md").write_text("# 细则\n禁止缩写\n", encoding="utf-8")

    learn_skill, _ = egent.builtin_tools.skill_tools.get_skill_tools(egent.agent.Agent._Agent__build_skills([skill_dir])[0])
    result = learn_skill("demo", "rules/detail.md")

    assert result.startswith("# 技能文件: demo/rules/detail.md")
    assert "禁止缩写" in result
    assert "演示技能" not in result
    assert "# SKILL.md" not in result


def test_learn_skill_rejects_path_escape(tmp_path) -> None:
    """learn_skill 不得读出技能目录外的文件。"""
    skill_dir = tmp_path / "demo"
    _write_skill(skill_dir, "demo", "演示")
    outside = tmp_path / "secret.md"
    outside.write_text("secret\n", encoding="utf-8")

    learn_skill, _ = egent.builtin_tools.skill_tools.get_skill_tools(egent.agent.Agent._Agent__build_skills([skill_dir])[0])
    with pytest.raises(ValueError, match="越界"):
        learn_skill("demo", "../secret.md")


def test_run_skill_script_only_allows_skill_directory(tmp_path) -> None:
    """run_skill_script 只能执行技能目录内脚本。"""
    skill_dir = tmp_path / "demo"
    outside = tmp_path / "outside.py"
    skill_dir.mkdir()
    outside.write_text("print('outside')\n", encoding="utf-8")
    script = skill_dir / "scripts"
    script.mkdir()
    (script / "main.py").write_text(
        "import sys\nprint(' '.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    _write_skill(skill_dir, "demo", "演示")

    _, run_skill_script = egent.builtin_tools.skill_tools.get_skill_tools(egent.agent.Agent._Agent__build_skills([skill_dir])[0])

    with pytest.raises(ValueError, match="越界"):
        run_skill_script("demo", "../outside.py")
    assert "hello world" in run_skill_script("demo", "scripts/main.py", ["hello", "world"])


def test_agent_injects_skill_catalog(tmp_path, monkeypatch) -> None:
    """Agent 构造时应写入技能摘要 system 消息。"""
    skill_dir = tmp_path / "demo"
    _write_skill(skill_dir, "demo", "演示技能")

    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
            thinking_mode="none",
        ),
    )

    agent = egent.agent.Agent(settings="test", skills=[skill_dir])

    assert agent._Agent__messages[0]["role"] == "system"
    assert "demo: 演示技能" in agent._Agent__messages[0]["content"]
    tool_names = {tool["function"]["name"] for tool in agent._Agent__api_tools}
    assert {"__bt_learn_skill", "__bt_run_skill_script"}.issubset(tool_names)


def test_skill_tools_register_with_resolve_tools(tmp_path) -> None:
    """技能工具应能被 resolve_tools 正常注册。"""
    skill_dir = tmp_path / "demo"
    _write_skill(skill_dir, "demo", "演示")
    tools = egent.builtin_tools.skill_tools.get_skill_tools(egent.agent.Agent._Agent__build_skills([skill_dir])[0])
    api_tools, _handlers, _conversation_terminating_tool_names = egent.tool.resolve_tools(tools)

    assert {tool["function"]["name"] for tool in api_tools} == {
        "learn_skill",
        "run_skill_script",
    }
    learn_schema = next(tool for tool in api_tools if tool["function"]["name"] == "learn_skill")
    assert learn_schema["function"]["parameters"]["properties"]["relative_path"]["default"] == "SKILL.md"
    handler = egent.tool.tool_handler_from_function(tools[0])
    result = handler(json.dumps({"skill_id": "demo"}))
    assert "演示" in result
    assert "# SKILL.md" in result
