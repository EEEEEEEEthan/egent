"""从运行目录/.egent/.model.toml 加载模型连接配置。"""
# pylint: disable=protected-access

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from typing import Any, Literal

import egent._constants

DEFAULT_CONFIG_PATH = egent._constants.EGENT_DIR / ".model.toml"

DEFAULT_CONFIG_TEMPLATE = """\
[gpt5-flash]
url = "OPENAI_URL"
model = "MODEL_NAME"
apikey = "OPENAI_KEY"
thinking = "reasoning_effort"  # none | reasoning_effort | enable_thinking | anthropic_thinking

[gpt5]
url = "OPENAI_URL"
model = "MODEL_NAME"
apikey = "OPENAI_KEY"
thinking = "reasoning_effort"
"""

ThinkingMode = Literal["none", "reasoning_effort", "enable_thinking", "anthropic_thinking"]

_THINKING_MODES: frozenset[str] = frozenset({
    "none",
    "reasoning_effort",
    "enable_thinking",
    "anthropic_thinking",
})

_REASONING_EFFORT_TOKEN_BUDGETS: dict[str, int] = {
    "low": 1024,
    "medium": 4096,
    "high": 16000,
}


class ConfigTemplateCreatedError(FileNotFoundError):
    """配置文件已自动创建，需用户填写后重试。"""


@dataclass
class ModelSettings:
    """指定 profile 的 API 连接参数。"""

    api_key: str
    base_url: str
    model_name: str
    profile_name: str
    thinking_mode: ThinkingMode = "none"

    @staticmethod
    def load(profile_name: str) -> ModelSettings:
        """读取指定 profile 的连接配置。

        若配置文件不存在，则创建模板并抛出 ``ConfigTemplateCreatedError``。
        """
        path = DEFAULT_CONFIG_PATH
        if not path.is_file():
            egent._constants.EGENT_DIR.mkdir(parents=True, exist_ok=True)
            egent._constants.ensure_egent_gitignore()
            path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
            raise ConfigTemplateCreatedError(
                f"已创建配置模板 {path}，请填写后重新运行",
            )
        try:
            profiles = tomllib.loads(path.read_text(encoding="utf-8"))
            section = profiles[profile_name]
            thinking_mode = section.get("thinking", "none")
            if thinking_mode not in _THINKING_MODES:
                raise ValueError(
                    f"thinking 无效: {thinking_mode!r}，"
                    f"可选 {_THINKING_MODES}",
                )
            return ModelSettings(
                api_key=section.get("apikey") or os.getenv("OPENAI_API_KEY"),
                base_url=section.get("url") or "https://api.openai.com/v1",
                model_name=section["model"],
                profile_name=profile_name,
                thinking_mode=thinking_mode,
            )
        except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"配置无效: profile={profile_name!r}") from error


def build_thinking_extra_body(
    thinking_mode: ThinkingMode,
    reasoning_effort: str | None,
) -> dict[str, Any] | None:
    """按 profile 的 thinking 模式，将 send() 的 reasoning_effort 映射为 extra_body。"""
    if thinking_mode == "none" or reasoning_effort is None:
        return None
    if thinking_mode == "reasoning_effort":
        return {"reasoning_effort": reasoning_effort}
    if thinking_mode == "enable_thinking":
        extra_body: dict[str, Any] = {"enable_thinking": True}
        token_budget = _REASONING_EFFORT_TOKEN_BUDGETS.get(reasoning_effort)
        if token_budget is not None:
            extra_body["thinking_budget"] = token_budget
        return extra_body
    if thinking_mode == "anthropic_thinking":
        token_budget = _REASONING_EFFORT_TOKEN_BUDGETS.get(reasoning_effort, 4096)
        return {
            "thinking": {
                "type": "enabled",
                "budget_tokens": token_budget,
            },
        }
    raise ValueError(f"未知 thinking 模式: {thinking_mode!r}")
