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

ThinkingMode = Literal["none", "reasoning_effort", "enable_thinking"]

# GLM enable_thinking / 同类接口的固定思考 token 上限
_THINKING_TOKEN_BUDGET = 4096


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
            return ModelSettings(
                api_key=section.get("apikey") or os.getenv("OPENAI_API_KEY"),
                base_url=section.get("url") or "https://api.openai.com/v1",
                model_name=model_name,
                profile_name=profile_name,
                thinking_mode=infer_thinking_mode(model_name),
            )
        except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"配置无效: profile={profile_name!r}") from error


def infer_thinking_mode(model_name: str) -> ThinkingMode:
    """按模型名推断 thinking 请求格式：GLM → enable_thinking，DeepSeek → reasoning_effort。"""
    model_key = model_name.casefold()
    if "glm" in model_key:
        return "enable_thinking"
    if "deepseek" in model_key:
        return "reasoning_effort"
    return "none"


def build_thinking_extra_body(
    thinking_mode: ThinkingMode,
    reasoning_effort: str | None,
) -> dict[str, Any] | None:
    """按 thinking 模式，将 send() 的 reasoning_effort 映射为 extra_body。"""
    if thinking_mode == "none" or reasoning_effort is None:
        return None
    if thinking_mode == "reasoning_effort":
        return {"reasoning_effort": reasoning_effort}
    if thinking_mode == "enable_thinking":
        return {
            "enable_thinking": True,
            "thinking_budget": _THINKING_TOKEN_BUDGET,
        }
    raise ValueError(f"未知 thinking 模式: {thinking_mode!r}")
