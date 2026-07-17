"""model_settings 单元测试。"""

from __future__ import annotations

import pytest

import egent.model_settings


def test_build_thinking_extra_body_none_mode() -> None:
    """none 模式不发送 thinking 参数。"""
    assert egent.model_settings.build_thinking_extra_body("none", "high") is None
    assert egent.model_settings.build_thinking_extra_body("reasoning_effort", None) is None


def test_build_thinking_extra_body_reasoning_effort_mode() -> None:
    """reasoning_effort 模式透传 OpenAI 风格参数。"""
    assert egent.model_settings.build_thinking_extra_body(
        "reasoning_effort",
        "high",
    ) == {"reasoning_effort": "high"}


def test_build_thinking_extra_body_enable_thinking_mode() -> None:
    """enable_thinking 模式映射为 DashScope/GLM 风格参数。"""
    assert egent.model_settings.build_thinking_extra_body(
        "enable_thinking",
        "high",
    ) == {
        "enable_thinking": True,
        "thinking_budget": 16000,
    }


def test_build_thinking_extra_body_anthropic_thinking_mode() -> None:
    """anthropic_thinking 模式映射为 Anthropic thinking 结构。"""
    assert egent.model_settings.build_thinking_extra_body(
        "anthropic_thinking",
        "medium",
    ) == {
        "thinking": {
            "type": "enabled",
            "budget_tokens": 4096,
        },
    }


def test_model_settings_load_thinking_mode(tmp_path, monkeypatch) -> None:
    """load 应解析 thinking 字段。"""
    config_path = tmp_path / ".egent" / ".model.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """
[leader]
url = "http://localhost/v1"
model = "glm-5.1"
apikey = "test-key"
thinking = "enable_thinking"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(egent.model_settings, "DEFAULT_CONFIG_PATH", config_path)

    settings = egent.model_settings.ModelSettings.load("leader")

    assert settings.thinking_mode == "enable_thinking"
    assert settings.model_name == "glm-5.1"


def test_model_settings_load_rejects_unknown_thinking_mode(tmp_path, monkeypatch) -> None:
    """未知 thinking 值应报错。"""
    config_path = tmp_path / ".egent" / ".model.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """
[leader]
model = "test"
thinking = "unsupported"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(egent.model_settings, "DEFAULT_CONFIG_PATH", config_path)

    with pytest.raises(ValueError, match="thinking 无效"):
        egent.model_settings.ModelSettings.load("leader")
