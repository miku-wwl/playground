# Mini AI Agent — Interview Cheat Sheet

## 一句话记住

**LLM 提议下一步，Agent Runtime 检查并执行；工具结果回到上下文，循环直到回答或触发限制。**

## 架构图

```text
User
  │ request
  ▼
AgentLoop ◄──────────────► MessageHistory
  │  asks for a decision         │ user / tool call / result
  ▼                              │
ModelClient (Ollama / Fake)      │
  │ tool_call(name, arguments)  │
  └──────────┬───────────────────┘
             ▼
       ToolDispatcher ── validates name, schema, identity, approval
             │
             ▼
       ToolRegistry ──> Python business tool ──> result

Agent events ──> JSONL Trace ──> Evaluation Runner ──> metrics
```

模型输出的是结构化决策，不会直接运行 Python。Dispatcher 才是实际调用工具的运行时代码。

## Agent Loop

```text
用户请求和上下文
      ↓
模型决定：tool_call 还是 final
      ├─ final → 返回答案并结束
      └─ tool_call → Dispatcher 校验并执行
                         ↓
                   工具结果写回 History
                         ↓
                     再问模型
```

Agent 必须有停止条件，例如 final answer、最大决策步数或超时。工具调用本身不代表成功；要检查工具结果。

## 十个核心术语

| Term | 面试时怎么解释 |
|---|---|
| Agent Loop | 反复进行模型决策、工具调用、观察结果，直到结束的循环。 |
| Tool Calling | 模型用结构化格式提出工具名和参数。 |
| Dispatcher | 应用中负责校验并实际执行工具调用的组件。 |
| Tool Registry | 运行时允许调用的工具清单。 |
| Structured Output | 要求模型按固定 JSON 结构返回决策。 |
| Schema Validation | 检查字段、类型和必填参数是否符合约定。 |
| Authentication | 确认当前用户是谁。 |
| Authorization | 判断当前用户能否执行某个操作。 |
| Human-in-the-loop | 重要操作暂停，等待人审核后再执行。 |
| Trace / Evaluation | Trace 记录一次运行；Evaluation 用预期结果检查一组场景。 |

## 常见概念区别

**Agent vs Workflow**：Workflow 按预先确定的步骤走；Agent 可以根据模型决策动态选择下一步。实际系统常用 Workflow 固定边界，把少数判断步骤交给 Agent。

**Function Calling vs MCP**：Function Calling 是模型提出函数调用的方式；MCP 是应用之间提供和调用工具、资源的协议。它们不是同一个东西，可以组合使用。本项目使用 Function Calling 风格的 JSON 决策和本地 Python 工具，没有实现 MCP。

**Memory vs State vs Trace**：Memory 给模型提供可参考的上下文；State 表示业务当前事实；Trace 记录运行中发生的事件。日志里记录了状态，不等于系统能从日志恢复状态。

**Single Agent vs Multi-Agent**：单 Agent 更容易控制、测试和排错。只有任务确实能拆成相对独立的专业工作时，再考虑 Multi-Agent；多个 Agent 会增加通信、状态协调和评估成本。

**Offline Evaluation**：离线跑固定场景并与预期结果比较，适合发布前回归。人工 Review 和 LLM-as-Judge 可辅助评价开放式回答；Judge 应用人工结果校准。权限和越权执行仍要用确定性检查。本项目只有小型固定场景，没有人工 Review 或 LLM Judge。

## 五道系统设计追问

**1. How would you design a safe support Agent?**
先从应用取得用户身份，再把有限的工具交给模型。Dispatcher 校验工具名和参数，并用运行时身份做授权。只读查询按权限执行；创建工单暂停等人批准。添加超时、步数限制、Trace 和回归评估。

**2. How do you handle prompt injection?**
不把 System Prompt 当权限边界。工具层独立校验身份、数据范围和参数；只执行注册工具。用攻击输入验证，即使模型提出危险调用，也不能读到无权访问的数据。

**3. How do you prevent duplicate side effects?**
为副作用请求设计幂等键，并在服务端持久化处理状态。重试同一个键时返回原结果，不重复创建。当前 Playground 只阻止同一审批 ID 被重复处理，没有实现持久化幂等。

**4. What if the model or a tool is slow or unavailable?**
对模型和工具分别设超时，并限制 Agent 步数。明确记录失败状态。读取操作可按策略重试；副作用不能未经幂等保护就盲目重试。

**5. How do you know a new model version is better?**
用固定的正常、边界、越权和故障场景比较版本，检查实际工具结果而不只看模型自述。结合成功率、工具选择、安全指标、人工抽查和生产监控。

## 90 秒英文介绍

> I built a small customer-support Agent to understand how tool calling works at runtime. A user request goes to an Agent loop, which asks a local Ollama model for a structured decision. The model can propose a balance lookup, an order lookup, or a support-ticket request, but it does not execute code. A dispatcher validates the tool and its arguments, passes a runtime user identity (fixed in this demo), and calls only registered tools. Ticket creation pauses for human approval. I added JSONL traces and a small evaluation runner as well. In my deterministic local suite, six scenarios passed, including an invalid tool call and a cross-user access attempt. In a separate run, phi4-mini passed five local scenarios and refused the cross-user request. These are results from a simulated learning project, not production results or a description of an employer's internal system.

## 面试前自测

1. 谁真正执行工具：LLM 还是 Dispatcher？
2. 为什么 JSON Schema 合法不代表用户有权限？
3. Trace 与 Evaluation 分别回答什么问题？
4. 如果工单处于 `PENDING_APPROVAL`，它是否已经创建？
5. 当前实验验证了什么，又没有验证什么？
