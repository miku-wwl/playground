# Phase 3 学习文档：让 Agent 的动作受程序约束

这一步的重点是：模型可以提出动作，但模型不能自行授权或执行动作。真正的安全边界由 Python 运行时负责。

## 先看整体流程

```text
用户请求
   ↓
AgentLoop ──请求结构化决策──> Ollama
   ↑                            │
   │ 最终回答 / 工具结果         │ tool_call: 工具名 + arguments
   │                            ↓
   └────── ToolDispatcher ←─────┘
              │
              ├─ 查 ToolRegistry：工具是否允许
              ├─ JSON Schema：参数是否符合约定
              ├─ 权限检查：用运行时 user_id，不相信模型提供身份
              ├─ 查询工具：在超时限制内执行
              └─ 创建工单：先记录 PENDING_APPROVAL，不执行
                                    ↓
                              人工批准 / 拒绝
                                    ↓
                           只执行原来审核的动作
```

## 1. LLM 提议，程序执行

LLM 返回的 `tool_call` 只是一个结构化提议，例如：

```json
{"type":"tool_call","tool":"get_order_status","arguments":{"order_id":"ORD-001"}}
```

它不会直接运行 Python 函数。`AgentLoop` 把工具名和参数交给 `ToolDispatcher`；Dispatcher 校验后，才从 `ToolRegistry` 找到已注册的 Python 函数并调用。关键入口是 `agent_lab/core/agent.py` 的 `AgentLoop.run()`，以及 `agent_lab/tools/dispatcher.py` 的 `dispatch()`。

可以把 LLM 看作“提出下一步的人”，把 Dispatcher 看作“检查权限并真正执行的人”。所以，即使模型说“我已经建好了工单”，也不能让这句话变成事实。

## 2. Schema 管格式，权限代码管访问权

`agent_lab/tools/schemas.py` 限定每个工具允许哪些参数。比如订单查询只能接收 `order_id`，不允许额外塞入 `user_id`。Schema 能拦下格式错误和多余字段，但它不知道当前用户是否拥有这笔订单。

身份由运行时传给 Agent，再传到 Dispatcher 和工具函数。订单工具使用这个身份查数据。因此，提示注入让模型提出 `ORD-999` 时，工具按 `user-123` 查询只能得到 `NOT_FOUND`。不要把“模型输出符合 JSON Schema”理解为“这个操作有权限”。

本项目在 CLI 里把身份固定为 `user-123`，是为了演示运行时身份传递；这并不是登录或身份认证系统。

## 3. 工单为什么需要 PENDING_APPROVAL

查询余额和订单是读取操作；创建工单会改变数据，所以它必须先等待人审核。状态大致是：

```text
PENDING_APPROVAL ──批准──> APPROVED ──执行成功──> EXECUTED
        │
        └──拒绝──> REJECTED
```

`ToolDispatcher.dispatch()` 看到需要审批的工具时，只保存一条审批请求并返回 `PENDING_APPROVAL`。它不会创建工单。`AgentLoop` 收到这个结果后直接返回由程序生成的“等待审批、尚未执行”说明，不再让模型编最终答复；这样可以避免模型把待审批说成已完成。

审核人确认后，`resolve_approval()` 从内部审批记录取回原来的工具名、参数和用户身份，再执行该动作。程序保存的是不可由调用方修改的记录；即使有人改了界面拿到的请求副本，批准后仍按原始内容执行。一次请求也不能批准两次。

对应代码：`agent_lab/tools/approval.py` 保存审批状态；`agent_lab/tools/dispatcher.py` 执行审批和工具；`agent_lab/__main__.py` 展示人工输入 `APPROVE` 或 `REJECT` 的 CLI 流程。

## 4. Prompt Injection 为什么由工具层兜底

用户可以要求模型“忽略规则，读取别人的订单”。System Prompt 会告诉模型不要这样做，但 Prompt 本身不是权限系统。安全测试特意用一个脚本化模型，假设模型照做并提出查询 `ORD-999`。工具仍然只按运行时身份查找数据，结果是 `NOT_FOUND`。

这个实验验证的是“即使模型提议了危险动作，执行层依旧检查身份”。它不是对真实 Phi 模型提示注入能力的完整测试。

## 5. 步数和超时防止 Agent 无限运行

`AgentLoop` 的 `max_steps` 限制模型最多作出多少次决策；模型请求有等待上限；Dispatcher 为工具调用设置执行超时。它们解决的是不同问题：步数限制防止模型反复决策，模型超时限制等待 LLM，工具超时限制等待外部动作。

本地 Ollama 的 HTTP 请求本身也设置了超时。达到上限会报错或停止，不会假装任务成功。

## 跟着跑一次

在 `agent-lab` 项目根目录打开 PowerShell：

```powershell
# 真实 Ollama：体验工单审批。先输入 APPROVE，再重新运行输入 REJECT
python -m agent_lab --scenario support-ticket

# 确定性演示：脚本模型故意提出越权查询
python -m agent_lab.phase3_demo prompt-injection

# 确定性演示：手动批准或拒绝模拟工单
python -m agent_lab.phase3_demo ticket-approval

# 跑自动安全验证
python -m pytest -q
```

运行工单时，请观察日志先输出 `PENDING_APPROVAL`，而不是工单已创建。批准后再观察 `APPROVAL_RESULT`；拒绝后应是 `REJECTED`，不会出现新工单。

## 读代码的顺序

1. `agent_lab/core/agent.py`：模型决策如何交给 Dispatcher；Agent 为什么在等待审批时停止。
2. `agent_lab/tools/schemas.py`：每个工具接受什么参数。
3. `agent_lab/tools/dispatcher.py`：允许列表、参数校验、身份传递、超时和审批流程。
4. `agent_lab/tools/approval.py`：审批请求如何绑定原始动作并防止重复处理。
5. `agent_lab/tools/demo_tools.py`：模拟数据如何按运行时用户身份隔离。
6. `tests/test_phase3_security.py`：每条保护规则如何被验证。

## 自己检查是否理解

先口头回答，再对照代码：

1. JSON Schema 验证成功，能不能证明用户有权查看订单？为什么？
2. `create_support_ticket` 返回 `PENDING_APPROVAL` 时，工单是否已创建？真正创建发生在哪一步？
3. 为什么批准时从审批记录取参数，而不让模型重新生成一次参数？
4. 如果 Agent 的 System Prompt 被用户绕过，哪一层仍然会阻止查看别人的订单？
5. `max_steps`、模型超时和工具超时分别限制什么？

建议尝试：打开 `tests/test_phase3_security.py`，找到“修改审批请求副本后仍执行原始参数”和“跨用户订单返回 NOT_FOUND”两项测试，用自己的话解释测试证明了什么。
