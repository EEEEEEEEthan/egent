"""从运行目录/.egent/.model.toml 加载模型连接配置。"""
# pylint: disable=protected-access

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass

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


class ConfigTemplateCreatedError(FileNotFoundError):
    """配置文件已自动创建，需用户填写后重试。"""


@dataclass
class ModelSettings:
    """指定 profile 的 API 连接参数。"""

    api_key: str
    base_url: str
    model_name: str
    profile_name: str

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
            return ModelSettings(
                api_key=section.get("apikey") or os.getenv("OPENAI_API_KEY"),
                base_url=section.get("url") or "https://api.openai.com/v1",
                model_name=section["model"],
                profile_name=profile_name,
            )
        except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"配置无效: profile={profile_name!r}") from error
