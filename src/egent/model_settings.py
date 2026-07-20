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

[gpt5]
url = "OPENAI_URL"
model = "MODEL_NAME"
apikey = "OPENAI_KEY"
"""

# reasoning_effort: DeepSeek 等；thinking: 火山 Coding Plan / Z.AI 的 thinking 对象
ThinkingMode = Literal["none", "reasoning_effort", "thinking"]

_THINKING_TOKEN_BUDGET = 8192
# 思考与正文共用输出额度，须为正文预留空间：max_tokens = budget + response
_RESPONSE_TOKEN_BUDGET = 8192


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
            model_name = section["model"]
            base_url = section.get("url") or "https://api.openai.com/v1"
            return ModelSettings(
                api_key=section.get("apikey") or os.getenv("OPENAI_API_KEY"),
                base_url=base_url,
                model_name=model_name,
                profile_name=profile_name,
                thinking_mode=infer_thinking_mode(model_name, base_url),
            )
        except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"配置无效: profile={profile_name!r}") from error


def infer_thinking_mode(model_name: str, base_url: str) -> ThinkingMode:
    """按端点与模型名推断：火山/Z.AI → thinking，DeepSeek → reasoning_effort。"""
    url_key = base_url.casefold()
    if "volces.com" in url_key or "z.ai" in url_key:
        return "thinking"
    if "deepseek" in model_name.casefold():
        return "reasoning_effort"
    return "none"


def resolve_completion_max_tokens(
    thinking_mode: ThinkingMode,
    reasoning_effort: str | None,
) -> int | None:
    """开启思考时返回 max_tokens（思考预算 + 正文预留）；否则不限制。"""
    if thinking_mode == "none" or reasoning_effort is None:
        return None
    return _THINKING_TOKEN_BUDGET + _RESPONSE_TOKEN_BUDGET


def build_thinking_extra_body(
    thinking_mode: ThinkingMode,
    reasoning_effort: str | None,
) -> dict[str, Any] | None:
    """按 thinking 模式，将 send() 的 reasoning_effort 映射为 extra_body。"""
    if thinking_mode == "none" or reasoning_effort is None:
        return None
    if thinking_mode == "reasoning_effort":
        return {"reasoning_effort": reasoning_effort}
    if thinking_mode == "thinking":
        return {
            "thinking": {
                "type": "enabled",
                "budget_tokens": _THINKING_TOKEN_BUDGET,
            },
        }
    raise ValueError(f"未知 thinking 模式: {thinking_mode!r}")
