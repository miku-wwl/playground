# AIG Hello World：独立 Consumer 入门项目

这个项目用 **Agentic Intent Gate v0.2.0 的真实公共 API**，演示一个最小可理解的 Agent 执行闭环：

```text
User Intent: "Hello from AIG!"
   |
   v
DeterministicHelloProvider     <- 模拟 LLM 生成 Plan，零 API Key
   |
   v
AIG Plan Validation            <- AIG 核心负责，不在这里重复实现
   |
   v
Persistent Run / Approval      <- CLI 让操作者看到准确 Plan，必须选 y
   |
   v
Action Admission               <- 绑定准确、已批准的 Plan
   |
   v
Independent Authorization      <- Capability + trusted Policy
   |
   v
Durable Claim / Gateway        <- CAS / effect_key，由 AIG 实施
   |
   v
GreetingExecutor               <- Consumer 自己实现的**唯一** Side Effect 工具
   |
   v
SQLite greeting + receipt      <- Consumer 拥有的独立效果数据库
```

**不使用 LangChain、LangGraph、Ollama、Claude 或 OpenAI**。避免在学习 AIG 的执行原理时被模型部署分散注意力。

## 环境要求

- Python **3.13**，Windows PowerShell（Linux/macOS 也可以）。
- `uv`：https://docs.astral.sh/uv/
- 首次安装依赖时需要可以访问 GitHub 和 PyPI / 对应包镜像。

AIG 依赖固定在已验证的 `v0.2.0` 提交：

`7261fdd2f47d2b15fabe8faac527eeee37338eb1`

安装的是上游仓库的 Python 包，不在这个 ZIP 里复制任何 AIG 核心代码。

## 运行（PowerShell）

```powershell
# 1. 在解压后的 aig-hello-world 目录中执行
uv sync

# 2. 首次运行：必须确认没有其他进程正在使用这个演示数据目录
uv run aig-hello run --message "Hello from AIG!" --data-dir .demo --predecessor-stopped

# 3. 看到生成的 Plan 后输入 y 进行人工审批，或 N 拒绝

# 4. 退出程序后仍可以查看持久化收据
uv run aig-hello show --data-dir .demo

# 5. 运行真正的 AIG Consumer 集成测试
uv run python -m unittest discover -s tests -v
```

如果想观察 Approval Gate 拒绝效果，可以先运行一次，在审批时输入 `n`；之后再独立运行一次并输入 `y`。

`--predecessor-stopped` 是你本人对 **已停止此前使用同一数据目录的进程及其辅助进程** 的确认；不能机械地在生产环境中跳过检查。

运行成功会自动创建：

```text
.demo/
  identity.json       # 六字段 Trusted ToolBinding（启动时固定）
  capability          # 本地秘密 Token，绝不提交
  gate.sqlite3        # AIG 自己持久化的 Runs / Approvals / Actions / Audit
  effects.sqlite3     # Hello Consumer 自己的 greetings / receipts
```

该目录在 `.gitignore` 中。不要分享真实的 `capability` 文件。

## 项目目录（按职责分包）

```text
aig-hello-world/
├── pyproject.toml                # AIG v0.2.0 固定 Git 依赖和 CLI 入口
├── README.md
├── AGENTS.md
├── .gitignore
├── .env.example
├── docs/
│   └── CODE_WALKTHROUGH.md
├── src/
│   └── aig_hello/
│       ├── __init__.py
│       ├── app/                  # 面向用户的入口和用例编排
│       │   ├── __init__.py
│       │   ├── cli.py            # CLI / 人工审批交互
│       │   └── workflow.py       # Run → Approval → Admission → Authorization → Execute
│       ├── adapters/             # Consumer 对 AIG Ports 的具体实现
│       │   ├── __init__.py
│       │   ├── planner.py        # 确定性 ModelProvider（无真实 LLM）
│       │   └── executor.py       # SQLite GreetingExecutor / Receipt Store
│       └── bootstrap/            # 依赖注入 / 可信组件组装
│           ├── __init__.py
│           └── runtime_factory.py
└── tests/
    └── test_integration.py       # AIG 真实公共接口集成测试
```

### 三个目录怎么理解？

- **`app/`**：对外呈现 CLI，并安排整个业务执行步骤；不直接写 SQLite。
- **`adapters/`**：实现可替换的 Plan 生成器和唯一的副作用工具；不会重新实现 AIG 安全机制。
- **`bootstrap/`**：Composition Root，注册可信工具、配置 Capability/Policy，将 Consumer 组件注入 AIG。

注意：`src/aig_hello` 是**独立 Consumer** 的代码，不是 AIG 核心 Runtime 的副本。

## 推荐阅读顺序

1. `README.md`：先看执行流程和责任边界。
2. `src/aig_hello/app/cli.py`：终端入口、Plan 展示和人工确认。
3. `src/aig_hello/bootstrap/runtime_factory.py`：为什么独立项目能通过公共 API 使用 AIG。
4. `src/aig_hello/app/workflow.py`：Approval → Admission → Authorization → Execution 的真实链路。
5. `src/aig_hello/adapters/planner.py`：模型如何仅提供一个待验证 Plan。
6. `src/aig_hello/adapters/executor.py`：真正产生副作用并持久化 Receipt。
7. `tests/test_integration.py`：通过测试观察批准/授权/幂等/恢复边界。

详细导读在 `docs/CODE_WALKTHROUGH.md`。

## 安全与限制

- 这是 **本地离线学习 Demo**，不是公网服务，也不是生产认证系统。
- 它使用 **确定性 ModelProvider** 而非真实 LLM。这是特意的：先看清 AIG 架构，再增加模型调用。
- CLI 的 `y` 是 Demo 人工批准，不能证明操作员真实身份。
- AIG v0.2.0 只执行启动时明确绑定的一个 `SIDE_EFFECT` 工具和一步 Action。
- 不能认为本地 SQLite 的 Receipt 能保证任意云端 API 的 exactly-once 效果。
- 不允许自动重试 `Unknown` 状态；示例只写本地 SQLite。
- 此项目不修改、不 fork、不复制 AIG 的源代码。
- 建议不要在此 Demo 的数据目录上运行不同版本 AIG 或多个进程。

## 安装失败怎么办？

- 确认 Python 是 3.13：`python --version`。
- 确认可以访问 GitHub：`git ls-remote https://github.com/miku-wwl/agentic-intent-gate.git`。
- 若 `uv sync` 无法下载依赖，先解决 GitHub 或 Python 包源网络问题；不用复制 AIG 源码作为变通。

> 验证说明：制作 ZIP 的环境无法访问 GitHub，因此无法安装上游 AIG 并现场执行集成测试；仓库的公共 API 和调用顺序已与 v0.2.0 的真实 `examples/consumer/app.py` 对照。你本机安装依赖后，运行上面的 `unittest` 才能完成真实 E2E 验证。
