"""model_settings 单元测试。"""

# pylint: disable=no-member

from __future__ import annotations

import egent.model_settings


def test_infer_thinking_mode_from_model_name() -> None:
    """按模型名自动区分 GLM / DeepSeek thinking 格式。"""
    assert egent.model_settings.infer_thinking_mode("glm-latest") == "thinking"
    assert egent.model_settings.infer_thinking_mode("GLM-5.1") == "thinking"
    assert egent.model_settings.infer_thinking_mode("deepseek/deepseek-v4-flash") == "reasoning_effort"
    assert egent.model_settings.infer_thinking_mode("gpt-5") == "none"


def test_build_thinking_extra_body_none_mode() -> None:
    """none 模式或不传 effort 时不发送 thinking 参数。"""
    assert egent.model_settings.build_thinking_extra_body("none", "high") is None
    assert egent.model_settings.build_thinking_extra_body("reasoning_effort", None) is None


def test_build_thinking_extra_body_reasoning_effort_mode() -> None:
    """DeepSeek：透传 reasoning_effort。"""
    assert egent.model_settings.build_thinking_extra_body(
        "reasoning_effort",
        "high",
    ) == {"reasoning_effort": "high"}


def test_build_thinking_extra_body_thinking_mode() -> None:
    """GLM / 火山 Coding Plan：thinking 对象 + 固定 budget_tokens。"""
    assert egent.model_settings.build_thinking_extra_body(
        "thinking",
        "high",
    ) == {
        "thinking": {
            "type": "enabled",
            "budget_tokens": 8192,
        },
    }
    assert egent.model_settings.build_thinking_extra_body(
        "thinking",
        "low",
    ) == {
        "thinking": {
            "type": "enabled",
            "budget_tokens": 8192,
        },
    }


def test_model_settings_load_infers_thinking_mode(tmp_path, monkeypatch) -> None:
    """load 应根据 model 推断 thinking_mode。"""
    config_path = tmp_path / ".egent" / ".model.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """
[leader]
url = "http://localhost/v1"
model = "glm-5.1"
apikey = "test-key"

[coder]
url = "http://localhost/v1"
model = "deepseek/deepseek-v4-flash"
apikey = "test-key"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(egent.model_settings, "DEFAULT_CONFIG_PATH", config_path)

    leader = egent.model_settings.ModelSettings.load("leader")
    coder = egent.model_settings.ModelSettings.load("coder")

    assert leader.thinking_mode == "thinking"
    assert coder.thinking_mode == "reasoning_effort"
