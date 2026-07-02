---
name: example-greet
description: 示例技能：通过 run_skill_script 调用 greet.py，向指定对象打印问候语。用于演示技能目录、脚本参数与 egent 技能工具链。
---

# 示例问候技能

## 何时使用

- 需要向某人输出格式化问候语
- 演示 `learn_skill` / `run_skill_script` 的调用方式

## 调用方式

先 `learn_skill("example-greet")` 查看目录与本文，再用 `run_skill_script` 执行：

```
run_skill_script(
    "example-greet",
    "scripts/greet.py",
    ["Alice"]
)
```

## 脚本参数

`scripts/greet.py` 使用 argparse，位置参数与选项如下：

| 参数 | 说明 |
|------|------|
| `name` | 必填，问候对象姓名 |
| `--title` | 可选，头衔前缀（如 `Dr.`） |
| `--repeat` | 可选，重复打印次数，默认 `1` |

示例：

```
run_skill_script("example-greet", "scripts/greet.py", ["Bob", "--title", "工程师", "--repeat", "2"])
```

输出示例：`Hello, 工程师 Bob!`（重复两行）
