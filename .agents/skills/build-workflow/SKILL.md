---
name: build-workflow
description: 用程序编排 egent 确定性工作流：通过 request_until_submit 收敛 agent 输出，再用 Python 控制流串联步骤。用于搭建编码/验收/开发等多步流程，或用户提到工作流、request_until_submit、submit_task 编排时。
---

# 搭建工作流

用 **Python 程序** 编排 **确定的流程**。agent 负责单步内的判断与执行；流程走向由你的代码决定。

## 做什么

1. 把任务拆成若干 **步骤函数**（`async def`）
2. 需要 agent 完成的步骤，用 `request_until_submit` 跑到 **submit 被调用** 为止，拿到结构化结果
3. 用普通 Python（`if` / `for` / `return` / 调用其他步骤）把步骤串起来

## 单步：收敛 agent 输出

```python
async def my_step(conversation: Conversation, input: str) -> tuple[bool, str]:
    conversation.add_message("system", input)
    submitted = await conversation.request_until_submit(
        {"success": (bool, "任务是否完成"), "summary": (str, "结果摘要")},
        tools,
        on_event=_common.print_stream_event,  # 可省略；不需要输出时不传
    )
    return submitted["success"], submitted["summary"]
```

要点：

- 第一个参数是 submit 参数规格 `字段名 -> (类型, 描述)`，即 agent 可见的提交接口；框架据此生成 `submit_task` 工具 schema 并校验参数
- `request_until_submit` 循环请求直到 agent 调用 `submit_task`，直接返回提交的参数 dict，之后该步结束，流程回到 Python
- submit 提醒由框架自动追加，system 消息里只需写任务本身
- 流式事件通过 `on_event` 回调外抛（如 `_common.print_stream_event` 打到终端），不传则静默执行
- 需要跨多轮保持上下文时，**复用同一个** `Conversation`；每步独立则 **新建** `Conversation`

## 编排：确定的流程

步骤函数返回后，用代码决定下一步：

```python
async def outer_workflow(description: str) -> str:
    for _ in range(max_retries):
        ok, msg = await step_a(conversation, description)
        if not ok:
            continue
        passed, feedback = await step_b(description)
        if passed:
            return f"完成: {feedback}"
        conversation.add_message("system", f"未通过: {feedback}")
    return "失败"
```

要点：

- 循环、分支、重试、调用子步骤——全部写在 Python 里，不交给 agent 即兴发挥
- 子工作流可写成 `async def`，在上层通过 **工具注册** 暴露给 agent（见 `examples/example_workflow_develop.py`）

## 新建工作流 checklist

```
- [ ] 定义每步的输入/输出类型（如 tuple[bool, str]）
- [ ] 写 submit 参数规格 dict，明确 agent 要提交哪些字段
- [ ] 选定 Conversation 复用或隔离策略
- [ ] 配置该步 tools 白名单
- [ ] 在 system 消息里写清任务（submit 提醒由框架自动追加）
- [ ] 用 if/for/return 把各步串成完整流程
- [ ] 需要时把子流程注册为 ToolCallable 供上层 agent 调用
```

## 参考实现

完整示例见 `examples/`：

| 文件 | 作用 |
|------|------|
| `example_workflow_coding.py` | 单步 + 程序侧后续动作 |
| `example_workflow_review.py` | 单步收敛为确定结果 |
| `example_workflow_develop.py` | 多步编排与子流程注册 |
| `_common.py` | 示例用打印封装（非必需） |

先读这些文件照抄结构，再按任务改 submit 字段、tools 和编排逻辑。
