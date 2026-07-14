"""将仓库 ``src`` 加入 ``sys.path``，便于直接 ``python examples/xxx.py``。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parent.parent / "src"
_SOURCE_ROOT_TEXT = str(_SOURCE_ROOT)

if _SOURCE_ROOT.is_dir() and _SOURCE_ROOT_TEXT not in sys.path:
    sys.path.insert(0, _SOURCE_ROOT_TEXT)
