#!/usr/bin/env python3
"""示例问候脚本：接收姓名与可选参数并打印问候语。"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="打印问候语")
    parser.add_argument("name", help="问候对象姓名")
    parser.add_argument("--title", default="", help="头衔前缀")
    parser.add_argument("--repeat", type=int, default=1, help="重复打印次数")
    arguments = parser.parse_args()
    if arguments.repeat < 1:
        print("错误：--repeat 必须 >= 1", file=sys.stderr)
        return 1
    target = f"{arguments.title} {arguments.name}".strip() if arguments.title else arguments.name
    for _ in range(arguments.repeat):
        print(f"Hello, {target}!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
