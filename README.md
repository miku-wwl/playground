# AIG Hello World — 极简学习版

这是一个真正依赖 **Agentic Intent Gate v0.2.0** 的独立 Consumer 项目，删除了上一版的 `cli.py`、`argparse`、`run/show` 子命令与多层子包。**入口只有 `main.py`。**

## 30 秒理解

```text
main.py（运行 & 人工批准）
  ├─ planner.py（生成 JSON Plan；当前是确定性 Python，不使用真实 LLM）
  ├─ runtime.py（组装 AIG；Run -> Approval -> Admission -> Authorization -> Execute）
  └─ executor.py（受 AIG 调度后，写 SQLite 并记录 Receipt）
```

**AIG 本身由 pip/uv 安装的依赖提供，不复制 AIG 核心源码。**

## Windows 上运行

要求：Python 3.13 和已安装的 `uv`；首次安装需要可访问 GitHub 和 Python 包源。

在解压后的 `aig-hello-world-simple` 根目录运行：

```powershell
uv sync
uv run python main.py
```

首次运行生成新的 `.demo/` 数据目录，打印 Plan，等待：

```text
[3] 是否批准这个准确的 Plan？[y/n]:
```

输入 `y` 并按 Enter，才会走完真实 AIG 的 Action Admission、独立 Authorization、Durable Claim 和 ToolExecutor。输入 `n` 明确拒绝；直接回车或中断不会替你记录审批决定。

**第二次运行：** 复用已有 `.demo` 时会先要求你确认上一进程和辅助进程都已停止。这是保留 AIG single-owner 安全机制的必要一步，并非另一个业务审批。

要修改消息，直接编辑 `main.py` 顶部：

```python
MESSAGE = "Hello from AIG!"
```

不需要任何 CLI 参数、Ollama、Phi-4-mini、API Key、LangChain 或 LangGraph。

想查看数据库结果，程序在成功后自动列出已保存的 greeting 与 receipt。你也可以使用 SQLite 数据库浏览器只读查看项目根目录的 `.demo/effects.sqlite3`；AIG 的内部状态在 `.demo/gate.sqlite3`。

运行集成测试：

```powershell
uv run python -m unittest discover -s tests -v
```

## 项目结构

```text
aig-hello-world-simple/
├── main.py                        # ① 最先看：入口、打印 Plan 和审批
├── pyproject.toml                 # AIG v0.2.0 固定 Git 依赖
├── README.md
├── .gitignore
├── src/
│   └── aig_hello/
│       ├── __init__.py
│       ├── planner.py             # ② 返回固定结构的 Plan JSON
│       ├── runtime.py             # ③ 真实 AIG 的连接和执行调用
│       └── executor.py            # ④ SQLite GreetingExecutor
└── tests/
    └── test_integration.py       # 四个真实 Runtime 集成测试
```

### 要弄懂的三个点

1. **Plan 不等于 Tool Call：** `planner.py` 只返回 JSON，AIG 会验证它。
2. **Approval 不等于 Authorization：** `main.py` 获取用户意见，`runtime.py` 里的 Gateway 仍执行 Action Admission 和单独授权。
3. **执行者是 Harness，不是 LLM：** `ActionExecutionGateway` 通过 `ExecutableRegistry` 调用 `GreetingExecutor.execute()`。

## 安全说明

- 数据目录固定为**项目根目录** `.demo`，和旧版你在 `src` 目录运行时产生的 `src/.demo` 不同。不会搬迁、删除或覆盖旧数据库。
- `predecessor_stopped=True` 仅在首次新建目录或用户明确确认旧进程已停止后传入；不要同时启动两个实例处理同一存储。
- `.demo` 包含秘密 capability，不要提交或共享。
- 只允许执行一个注册的 `write_greeting` SIDE_EFFECT 工具，使用真实 AIG v0.2.0 API。
- 没有自动重试或 Unknown 恢复，也没有真实云端副作用；本地 SQLite Receipt 不代表远程 API 的 Exactly Once。
- 输入 y 是本地教学用的人工确认，并不构成生产环境真实身份认证。

**依赖固定提交：** `7261fdd2f47d2b15fabe8faac527eeee37338eb1`（`agentic-intent-gate==0.2.0`）。
