"""model_settings 单元测试。"""

# pylint: disable=no-member

from __future__ import annotations

import egent.model_settings

_VOLCES_CODING_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
_ZAI_URL = "https://api.z.ai/api/paas/v4"
_LITELLM_URL = "https://developer.coconut.is:1073/v1"


def test_infer_thinking_mode_from_url_and_model_name() -> None:
    """火山 / Z.AI 用 thinking 对象；其他端点仅 DeepSeek 用 reasoning_effort。"""
    assert egent.model_settings.infer_thinking_mode("glm-5.1", _VOLCES_CODING_URL) == "thinking"
    assert egent.model_settings.infer_thinking_mode("ark-code-latest", _VOLCES_CODING_URL) == "thinking"
    assert egent.model_settings.infer_thinking_mode("GLM-5.1", _ZAI_URL) == "thinking"
    assert egent.model_settings.infer_thinking_mode(
        "deepseek/deepseek-v4-flash",
        _LITELLM_URL,
    ) == "reasoning_effort"
    assert egent.model_settings.infer_thinking_mode("glm-5.1", _LITELLM_URL) == "none"
    assert egent.model_settings.infer_thinking_mode("gpt-5", _LITELLM_URL) == "none"


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


def test_resolve_completion_max_tokens_reserves_response_room() -> None:
    """开启思考时 max_tokens 须大于 thinking 预算，给正文留空间。"""
    assert egent.model_settings.resolve_completion_max_tokens("none", "high") is None
    assert egent.model_settings.resolve_completion_max_tokens("thinking", None) is None
    assert egent.model_settings.resolve_completion_max_tokens("thinking", "high") == 16384
    assert egent.model_settings.resolve_completion_max_tokens("reasoning_effort", "high") == 16384


def test_model_settings_load_infers_thinking_mode(tmp_path, monkeypatch) -> None:
    """load 应根据 url + model 推断 thinking_mode。"""
    config_path = tmp_path / ".egent" / ".model.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        f"""
[leader]
url = "{_VOLCES_CODING_URL}"
model = "glm-5.1"
apikey = "test-key"

[coder]
url = "{_LITELLM_URL}"
model = "deepseek/deepseek-v4-flash"
apikey = "test-key"

[proxy-glm]
url = "{_LITELLM_URL}"
model = "glm-5.1"
apikey = "test-key"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(egent.model_settings, "DEFAULT_CONFIG_PATH", config_path)

    leader = egent.model_settings.ModelSettings.load("leader")
    coder = egent.model_settings.ModelSettings.load("coder")
    proxy_glm = egent.model_settings.ModelSettings.load("proxy-glm")

    assert leader.thinking_mode == "thinking"
    assert coder.thinking_mode == "reasoning_effort"
    assert proxy_glm.thinking_mode == "none"
