# 源码导读：自上而下看懂 Hello AIG

> 这不是 LangChain / LangGraph 项目，也不是自己重新实现 AIG。
> 它只是一个使用 **已发布 AIG v0.2.0** 的独立 Consumer。

## 1. 三个子包 + 一个外部 AIG 依赖

```text
app/cli.py                         [启动入口 + 展示 Plan + 询问 y/N]
   ├── bootstrap/runtime_factory.py [Composition Root]
   │    ├── adapters/planner.py      [ModelProvider: 生成确定性 Plan]
   │    ├── adapters/executor.py     [ToolExecutor: 可信 SQLite Side Effect]
   │    └── agentic_intent_gate      [从独立 Python 依赖导入的 Runtime]
   └── app/workflow.py              [Run → Approval → Admission → Authorization → Execute]
```

这里是以学习为目的的三个内聚子包，而不是套用所有大型 Clean Architecture 分层：

| 子包 | 主要职责 | 不负责 |
| --- | --- | --- |
| `app/` | CLI 和用例流程 | 注册受信任执行器、持久化数据 |
| `adapters/` | 规划建议、具体工具副作用、Receipt 数据库 | 人工审批/授权/CAS |
| `bootstrap/` | 可信组件身份和 AIG Runtime 组装 | 具体业务流程和执行副作用 |

### 入口：`pyproject.toml` → `app/cli.py`

`[project.scripts]` 的 `aig-hello` 指向 `aig_hello.app.cli:main`，因此即使 CLI
模块被移动，原有启动命令 `uv run aig-hello run ...` 也不变。

### `bootstrap/runtime_factory.py`：构建 Composition Root

- `ToolBinding`：固定 tool/version/adapter/revision/target/scope 六个字段。
- `ToolCapability`：限制唯一工具以及严格参数 JSON Schema。
- `ExecutableRegistry`：注册可信 Executor。
- `CapabilityVerifier`：本地 Bearer 能力凭据（不是生产 IAM）。
- `BoundCapabilityAuthorization`：可信主体、操作、绑定与策略校验。
- `open_runtime(...)`：把 Provider、Executor、Policy 注入 AIG。

### `adapters/planner.py`：规划端适配器

返回结构化 Plan JSON。它不执行副作用、也不接触 SQLite。这个入门版刻意不使用
真实 LLM；后续可以单独添加云端或 Ollama Provider 而不修改 AIG 核心。

### `app/workflow.py`：串联业务步骤

1. `create(Intent(...))` → AwaitingApproval
2. `decide(APPROVE/REJECT, expected_version)` → Approved/Rejected
3. `gateway.admit(...)` → Pending Action
4. `gateway.authorize(...)` → Authorized Action
5. `gateway.execute(...)` → durable claim → ToolExecutor → Succeeded/Failed/Unknown

最重要的边界：`Approval != Authorization != Execution`。

### `adapters/executor.py`：副作用实现

GreetingExecutor 作为唯一注册的 trusted ToolExecutor，验证绑定与参数，并在
SQLite effect store 中把 greeting 与唯一 Receipt 在同一个事务内提交。
同一 effect_key 和同一 payload 复用原 Receipt；冲突拒绝；歧义保留 Unknown。

### `app/cli.py`：审批的交互层

展示 Plan，询问 `Approve? [y/N]` 后才调用 `approve_or_reject`。这里的 `y` 代表
本地演示同意，不证明真实用户身份。

### `tests/test_integration.py`：核心属性检查

通过实际 AIG v0.2.0 依赖验证：审批/执行成功、拒绝无副作用、Approval 不等于
Authorization、同一 Effect Key 的幂等以及重启后的持久化。

## 2. 两套持久化数据

- `.demo/gate.sqlite3`：由 AIG 管理的 Run/Approval/Action/Claim/授权/Audit 数据。
- `.demo/effects.sqlite3`：由这个示例管理的 greeting/receipt 数据。

`.demo/capability` 是本地私有 Token，不应复制或提交。
`.demo/identity.json` 包含稳定的 execution_scope 和 ToolBinding 身份。

## 3. 动手实验

1. 输入 `N`：观察 Rejected，效果数据库没有新增记录。
2. 输入 `y`：观察 Approved → Action Succeeded 和 Receipt。
3. 运行 `show`：验证终端进程退出后，Receipt 仍能被查询。
4. 阅读 `tests/test_integration.py`：批准不等于授权，直接执行 Pending Action 应被拒绝。
5. 更改 `--message` 再执行：产生一个**全新的 Run/Action**，不是重试旧的 Effect。

## 4. 不要误读

- v0.2.0 仅支持一个可信、启动时固定注册的 SIDE_EFFECT 工具及一步执行。
- Local bearer capability != production user authentication。
- 这个 SQLite 本地示例不证明第三方 API 的 exactly-once 语义。
- 真实执行超时或结果歧义必须 fail closed；不要擅自把 Unknown 当 Failed 重试。
- `--predecessor-stopped` 代表操作员已经确认旧的 owner 进程停止；它不是停机指令。
