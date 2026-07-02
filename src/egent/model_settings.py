"""从运行目录/.egent/.model.toml 加载模型连接配置。"""

from __future__ import annotations

import os
import pathlib
import tomllib
from dataclasses import dataclass

EGENT_DIR = pathlib.Path.cwd() / ".egent"
DEFAULT_CONFIG_PATH = EGENT_DIR / ".model.toml"
EGENT_GITIGNORE_ENTRIES = (".model.toml", "/.temp/", "/.logs/")

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


def ensure_egent_gitignore() -> None:
    """确保 ``.egent/.gitignore`` 包含模型配置与临时目录忽略项。"""
    EGENT_DIR.mkdir(parents=True, exist_ok=True)
    gitignore_path = EGENT_DIR / ".gitignore"
    if not gitignore_path.is_file():
        gitignore_path.write_text(
            "\n".join(EGENT_GITIGNORE_ENTRIES) + "\n",
            encoding="utf-8",
        )
        return
    existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    missing_entries = [
        entry for entry in EGENT_GITIGNORE_ENTRIES if entry not in existing_lines
    ]
    if not missing_entries:
        return
    gitignore_path.write_text(
        "\n".join(existing_lines + missing_entries) + "\n",
        encoding="utf-8",
    )


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
            EGENT_DIR.mkdir(parents=True, exist_ok=True)
            ensure_egent_gitignore()
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
