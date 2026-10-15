# Phase 3 验收报告

日期：2026-10-15

项目：Mini Trading Support Agent（本地 Playground）

验收范围：Agent 工具参数校验、运行时用户权限、人工审批、提示注入防护、调用限制，以及 Phase 2 回归。没有开始 Phase 4。

## 验收结论

**Phase 3：PASS（教学实验范围）**。自动测试、真实本地 Ollama 的 Phase 2 场景、工单审批通过与拒绝、以及确定性的跨用户提示注入演示均已执行。此结论只覆盖本地模拟程序，不代表生产级身份认证、持久化审批或真实交易所系统。

## 验收项目与证据

| 要求 | 结果 | 验证证据 |
|---|---|---|
| 每个工具有明确参数 Schema | PASS | `agent_lab/tools/schemas.py` 定义三个工具的字段、类型、必填项与额外字段拒绝规则；Ollama 决策也使用 JSON Schema。 |
| Dispatcher 校验工具名与参数 | PASS | 未注册工具抛出拒绝错误；缺少字段、错误资产、额外传入 `user_id` 等参数被拒绝。 |
| 身份来自运行时，而非模型参数 | PASS（演示边界） | Agent 将运行时 `authenticated_user_id` 交给 Dispatcher；工具 Schema 不接受 `user_id`。CLI 当前固定传入 `user-123`，不是实际登录认证。 |
| 阻止跨用户查询订单 | PASS | 提示注入脚本让模型提议查询 `ORD-999`；以 `user-123` 身份执行结果为 `NOT_FOUND`。测试对比确认 `user-456` 才能看到 `OPEN`。 |
| 创建工单前需要人工批准 | PASS | 真实 Ollama 提议 `create_support_ticket` 后，Agent 输出 `PENDING_APPROVAL` 并明确说明尚未执行。输入 `APPROVE` 后结果为 `EXECUTED`、工单号 `TICKET-001`；输入 `REJECT` 后结果为 `REJECTED`，没有工单结果。 |
| 批准只执行已审核的原始参数 | PASS | 自动测试修改调用方拿到的审批请求副本，再批准；最终工单仍使用审批时保存的原始订单号和原因。重复审批被拒绝。 |
| 非法调用默认拒绝 | PASS | 覆盖非法工具名、非法/多余参数、缺少认证身份和拒绝后的重复批准。 |
| 有限步数与超时 | PASS | Agent 的最大决策步数、模型等待时间、工具执行超时均有测试覆盖。 |

## 实际执行记录

- `python -m pytest -q`：**21 passed**。
- `python -m compileall -q agent_lab`：通过。
- `git diff --check`：通过。
- 真实 `phi4-mini:latest` + Ollama：余额查询得到 `500 USDT`；订单查询得到 `FILLED`；未支持的比特币价格预测返回受限说明。
- 真实 `phi4-mini:latest` + Ollama：工单请求先停在 `PENDING_APPROVAL`。分别输入 `APPROVE` 和 `REJECT`，实际结果分别为 `EXECUTED` / `TICKET-001` 和 `REJECTED`。
- 提示注入演示使用**脚本化恶意模型提议**，不是声称真实 Phi 模型已经被提示注入攻击。脚本提议跨用户查询后，权限仍由工具执行层返回 `NOT_FOUND`。

## 技术边界

订单、余额、工单和审批都存放在当前进程的内存中；进程退出后会清空。CLI 的用户身份 `user-123` 与审批人 `local-operator` 是教学固定值，不具备真实认证能力。提示注入演示用于验证执行层授权，不是完整红队评估。代码没有加入持久化审批、审计 JSONL、多用户登录或生产部署机制；这些不属于本 Phase 的验收范围。
