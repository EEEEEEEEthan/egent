"""将仓库 ``src`` 和项目根目录加入 ``sys.path``，便于直接 ``python examples/xxx.py``。"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_ROOT = _PROJECT_ROOT / "src"
_SOURCE_ROOT_TEXT = str(_SOURCE_ROOT)
_PROJECT_ROOT_TEXT = str(_PROJECT_ROOT)

if _SOURCE_ROOT.is_dir() and _SOURCE_ROOT_TEXT not in sys.path:
    sys.path.insert(0, _SOURCE_ROOT_TEXT)
if _PROJECT_ROOT_TEXT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_TEXT)
