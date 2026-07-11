# egent

AI Agent 框架，支持多轮对话、工具调用、自动代码执行与工作流编排。

## 安装

```bash
pip install -e .
```

从 GitHub 安装：

```bash
pip install git+https://github.com/EEEEEEEEthan/egent.git
```

开发测试依赖：

```bash
pip install -e ".[dev]"
```

## 快速开始

### 1. 配置模型

在项目根目录创建 `.egent/.model.toml`：

```toml
[gpt5-flash]
url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
apikey = "sk-xxxxxxxxxxxxxxxx"

[gpt5]
url = "https://api.openai.com/v1"
model = "gpt-4o"
apikey = "sk-xxxxxxxxxxxxxxxx"
```

### 2. 运行示例

运行 `examples/` 下的示例即可，例如：

```bash
python examples/example_agent.py
```

## 使用指南

### 内置工具

#### 文件系统工具（`builtin_tools/file_system_tools.py`）

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容 |
| `walk_files` | 遍历目录文件树 |
| `search_directory` | 在目录中按正则搜索（仅可发现且可读的文件） |
| `search_file` | 在指定文件中按正则搜索（仅可读文件） |
| `create_file` | 创建新文件 |
| `append_text` | 向文件追加文本 |
| `rewrite` | 重新写入文件 |
| `replace` | 正则替换文件内容 |
| `apply_patch` | 精确文本匹配替换 |
| `delete` | 删除文件或目录 |

#### Git 工具（`builtin_tools/git_tools.py`）

**只读工具**：`status`, `log`, `diff`, `branch`, `remote`, `tag`

**写入工具**：`init`, `clone`, `add`, `commit`, `push`, `pull`, `fetch`, `checkout`, `merge`, `reset`, `stash`

#### Shell 工具（`builtin_tools/shell_tools.py`）

执行任意 Shell 命令并返回 stdout / stderr / 退出码。

#### 技能工具（`builtin_tools/skill_tools.py`）

| 工具 | 说明 |
|------|------|
| `learn_skill` | 读取技能文件；缺省 `SKILL.md`（附目录树），可传相对路径读其他文件 |
| `run_skill_script` | 运行技能脚本 |

### 技能系统

`.agents/skills/` 目录下每个子目录是一个技能，包含：

- `SKILL.md` — 含 YAML frontmatter 的技能说明
- 脚本文件可放在技能目录下任意位置，`run_skill_script` 传入相对路径即可调用

### 路径安全

`Agent` 通过 ``path_permissions`` 字段控制内置文件工具的路径权限；写入能力由 ``editable`` 白名单与黑名单决定。权限变化后下次 ``request()`` 会自动追加「路径权限已更新」system 消息（与工具集变更提示类似）。

``examples/_common.py`` 中的 ``create_egent_path_permissions()`` 返回 ``PathPermissions``，用白名单与黑名单控制可发现、可读、可编辑。模式使用 fnmatch 全路径匹配（``*`` 可跨越路径分隔符）；``*`` 白名单表示全路径放行，项目目录黑名单使用解析后的绝对路径。目录搜索要求可发现且可读，文件搜索仅要求可读。``list_path_permissions`` 工具可列出当前规则。

### 工作流

| 示例 | 说明 |
|------|------|
| `example_agent.py` | 交互式 Agent CLI，集成所有工具 |
| `example_workflow_develop.py` | 主管委派 → 编码 → 验收循环 |
| `example_workflow_coding.py` | 编码实现 |
| `example_workflow_review.py` | 代码验收 |

### 模型配置

`.egent/.model.toml` 使用 TOML 格式配置多个 profile（如 `gpt5`, `gpt5-flash`），每个 profile 包含：

- `url` — API 端点
- `model` — 模型名称
- `apikey` — API 密钥

## 项目结构

```
├── .agents/skills/          # 技能目录
│   ├── build-workflow/
│   └── example-greet/
├── .egent/                  # 项目配置与运行时数据
│   ├── .model.toml          # 模型配置（不提交到 Git）
│   ├── .logs/               # 日志文件
│   └── .temp/               # 临时文件
├── examples/                # 工作流示例
│   ├── _common.py           # 共享辅助代码（路径校验器等）
│   ├── example_agent.py     # 交互式 Agent CLI
│   ├── example_workflow_develop.py
│   ├── example_workflow_coding.py
│   └── example_workflow_review.py
├── src/egent/               # 核心库
│   ├── __init__.py
│   ├── agent.py               # Agent 管理
│   ├── tool.py              # 工具 schema 生成
│   ├── model_settings.py    # 模型配置加载
│   ├── limits.py            # 限制常量
│   ├── _line_position.py    # 行位置工具
│   └── builtin_tools/       # 内置工具实现
│       ├── file_system_tools.py
│       ├── git_tools.py
│       ├── shell_tools.py
│       ├── skill_tools.py
│       ├── path_validator.py
│       └── command_utils.py
├── tests/                   # 单元测试
├── pyproject.toml
└── .todo                    # 待办事项
```

## 依赖

- Python >= 3.13
- openai >= 1.68.0
