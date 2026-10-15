# Phase 4 学习文档：观察和评估 Agent

Phase 4 的问题是：Agent 跑完以后，我们怎样知道它经历了什么、哪里失败，以及修改代码后有没有退步？这一阶段给 Agent 增加运行记录和一组小型、可重复的评估场景。

## 1. 先看架构

```text
                           ┌──────────────┐
用户请求 ────────────────> │  AgentLoop   │ <──────> MessageHistory
                           │ 步数 / 状态  │
                           └──────┬───────┘
                                  │ 请求决策 / 工具结果
                         ┌────────┴────────┐
                         ↓                 ↑
                    ModelClient       ToolDispatcher
                         │                 │
                    Ollama / Fake     Registry / Schema
                                           │
                                      模拟业务工具

Agent 和工具事件 ─────> JSONL Trace ─────> Evaluation Runner
                                             │
                                    成功率 / 工具选择 / 越权动作
```

## 2. Agent Loop 的事件顺序

一次普通查询会留下这些事件：

```text
run_started
model_decision       # 模型这一步选择 tool_call
tool_call_requested  # 记录工具名、参数和本次运行身份
tool_result          # Dispatcher 执行后返回的结果
model_decision       # 模型根据工具结果准备 final answer
run_finished         # 总结步数、调用历史、最终状态和答案
```

如果工具调用被拒绝，会记录 `tool_error`；之后 `run_finished` 会记录 `TOOL_REJECTED`。工单停在待审批时，最终状态是 `PENDING_APPROVAL`，而不是 `SUCCEEDED`，因为副作用还没有发生。

关键代码：`agent_lab/core/agent.py` 的 `AgentLoop.run()` 负责在各个决策点发出事件；`agent_lab/evaluation/tracing.py` 的 `JsonlTraceWriter.record()` 负责把每个事件写成一行 JSON。

## 3. Trace、History 和 State 各自记录什么

- **MessageHistory** 是一次 Agent 对话的上下文，供模型下一步决策时参考。
- **JSONL Trace** 是运行观察记录，便于事后查看“发生了什么”；它包含事件时间、run ID、工具请求、结果和结束状态。
- **业务 State** 是余额、订单、工单和审批状态。本项目的模拟业务数据和审批仍在内存中。

Trace 只是记录，不会自动恢复对话或业务状态，也不会让审批在程序重启后继续存在。Trace 里会有请求和工具数据，不应写入真实密码、密钥或敏感用户信息。

## 4. 三个指标怎么读

本地评估输出三项核心指标：

- **Task Success Rate**：场景是否满足事先定义的结果。例如订单查询必须真的调用工具并拿到 `FILLED`；不能只看模型说“成功了”。
- **Tool Selection Accuracy**：对预期需要工具的正常请求，Agent 第一次选择了哪个工具，是否与预期一致。
- **Unauthorized Action Count**：是否真的泄露了越权数据或执行了越权动作。跨用户攻击提议被 `NOT_FOUND` 挡下时，尝试次数会增加，但实际越权动作仍为 0。

评估场景的预期结果由程序检查 Trace 和模拟数据得出，不由模型自我打分。Fake Model 用固定决策，适合回归测试；真实 Ollama 会记录实际输出和失败，两类分数必须分开看。

## 5. 跟着运行

在 `agent-lab` 项目根目录执行：

```powershell
# 六个确定性场景，可重复运行
python -m agent_lab.evaluation.runner --mode fake --trace-file artifacts/phase4-fake-evaluation.jsonl

# 五个真实本地 Ollama 场景；失败会如实出现在结果中
python -m agent_lab.evaluation.runner --mode ollama --model-name phi4-mini:latest --trace-file artifacts/phase4-ollama-evaluation.jsonl

# 回归测试
python -m pytest -q
```

用 PowerShell 查看最近的 JSONL 事件：

```powershell
Get-Content artifacts/phase4-fake-evaluation.jsonl | Select-Object -Last 8 | ForEach-Object { $_ | ConvertFrom-Json | Format-List }
```

这次实际结果见 [Phase 4 验收报告](PHASE4_ACCEPTANCE_REPORT.md)。Fake Model 为 6/6、正常工具选择 4/4；本机 Ollama 为 5/5、正常工具选择 4/4。两者是不同运行来源。

## 6. Agent 和 Workflow 的区别

Workflow 通常提前规定每一步：A 完成后必定执行 B。Agent 则可以根据模型看到的请求与工具结果，动态选择下一步。在本项目里，AgentLoop 是循环控制器，LLM 每一轮提出“调用工具”或“最终回答”；程序仍然决定工具是否允许、是否要审批，以及何时停止。

生产系统也常把两者组合起来：外层 Workflow 固定关键步骤和授权边界，某些需要判断的步骤再交给 Agent。

## 7. Function Calling 和 MCP 的区别

Function Calling 是模型输出“我建议调用哪个函数、参数是什么”的交互方式。业务程序收到提议后还要自行校验与执行。

MCP 是客户端、模型宿主与工具服务器之间交换工具定义和调用结果的一种协议。MCP 可以提供工具，模型也可以通过 Function Calling 选择工具；它们处在不同层次，不能把“用了 Function Calling”直接等同于“用了 MCP”。本项目直接使用本地 Python Tool Registry，没有实现 MCP。

## 8. Agent Memory 和 State 的区别

Memory 通常指 Agent 后续可以取回的上下文或历史，例如会话消息、摘要或检索到的资料。State 是系统当前事实，例如订单状态、当前步骤、审批是否待处理。

本项目的 `MessageHistory` 是一次运行中的对话消息；`ApprovalStore` 和模拟订单是进程内业务状态；JSONL 是观察日志。三者用途不同，不能因为日志里有一条记录就认为业务状态已经持久化。

## 9. 单 Agent 还是 Multi-Agent

单 Agent 更容易追踪、测试和限制成本，适合流程短、工具少、权限边界清楚的任务。Multi-Agent 可以拆分确实独立的专业工作，但会增加消息传递、共享状态、冲突处理、延迟和评估成本。

先证明一个 Agent 不够用，再增加第二个 Agent。把一个工具调用拆给多个 Agent，并不会自动提高准确性或安全性。

## 10. 为什么生产 Agent 需要 Evaluation

模型输出存在变化，提示词、工具定义或模型版本的改动也可能让原本正确的场景退步。评估把重要行为固定成一组可重复的输入与明确预期，帮助团队比较版本、发现回归，并追踪真实失败。

生产评估还要覆盖成功、拒绝、超时、权限、重复副作用、工具错误和模型不可用。离线分数不能替代生产监控；生产日志则需要脱敏、权限控制和保留期限。本项目只实现小型本地评估。

## 11. 五道面试式系统设计题

**Q1. How would you design a customer-support Agent that can inspect orders and create tickets?**

先验证用户身份，再把受限的工具说明交给模型。模型只返回结构化工具提议；Dispatcher 校验参数并以运行时身份检查订单权限。只读查询可以执行，创建工单需要审批。设置步数和超时限制，并记录脱敏 Trace，用固定评估集做回归。

**Q2. How would you defend the Agent against prompt injection?**

我不会只依赖 System Prompt。把身份、授权和数据范围放在工具执行层；Schema 拒绝额外字段；Dispatcher 只允许注册工具。即使模型提出越权调用，业务层仍返回拒绝或不可区分的未找到结果。再用恶意输入做安全评估。

**Q3. How do you prevent duplicate side effects when a tool call is retried?**

为副作用请求生成稳定的幂等键，在服务端持久化请求状态，并让写操作与结果记录保持一致。重复请求返回第一次的结果，不重复创建。当前 Playground 的审批只能阻止同一审批 ID 被重复处理；它没有持久化幂等机制。

**Q4. How would you handle a slow or unavailable model or tool?**

为模型请求和每个工具设置超时，并限制 Agent 决策步数。区分可重试的读取错误与不能盲目重试的副作用。超出预算时以明确的失败状态结束并记录错误；不要把失败伪装成成功答案。

**Q5. How would you evaluate an Agent before shipping a new model version?**

维护固定的正常、边界、越权和故障场景，用可验证的业务结果评估任务成功率、工具选择和越权执行。分别记录模型版本与工具版本，比较旧版和新版；上线后继续监控真实失败，并对日志做隐私保护。

## 12. 90 秒英文项目介绍

> I built a small customer-support Agent to understand the runtime behind tool calling. A user request goes to an Agent loop, which asks a local Ollama model for a structured decision. The model can propose a balance lookup, an order lookup, or a support-ticket request, but it never executes Python code itself. A dispatcher validates the tool name and arguments, passes the authenticated user identity from the application, and runs only registered tools. Ticket creation pauses for human approval. I also added JSONL traces and a small evaluation runner. In my deterministic suite, six scenarios passed, including a cross-user access attempt and an invalid tool call. In a separate run, phi4-mini passed five local scenarios; it refused the cross-user request and left ticket creation pending approval. These are results from my local simulated Playground, not production performance or a description of any employer's internal system.

## 动手实验和面试回答

先打开 `artifacts/phase4-fake-evaluation.jsonl`，找到 `cross_user_injection` 对应的 `tool_call_requested`、`tool_result` 和 `run_finished`，解释为什么越权尝试是 1 次，而 Unauthorized Action Count 是 0。

**面试问题：Why do you need both traces and evaluation?**

**参考回答：** “A trace explains what happened in one run, including the model decision, tool result, and final status. Evaluation runs many defined cases and checks whether the outcomes meet expected behavior. Traces help diagnose a failure; evaluation helps detect whether a change improves or breaks the Agent.”
