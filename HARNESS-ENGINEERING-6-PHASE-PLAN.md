# Mini Coding Agent Harness：六阶段实践与学习计划

## 目标与边界

在 `playground/harness-lab/` 从零实现一个小型、可运行的 Coding Agent Harness，用真实执行和测试理解 Harness 如何为 Coding Agent 提供上下文、管理代码变更、施加策略、验证结果并记录过程。重点是理解和面试表达，不追求代码量或复刻 Codex、Claude Code。

本练习与已经完成的 Agent Engineering 学习项目相互独立。Harness 里的 Agent 使用确定性的 Mock，不接入真实 LLM；Mock 负责提出候选修改，Harness 负责管理工作区、执行允许的测试、检查策略、处理审批和判断任务结果。不得修改 Playground 中的其他项目。

技术约束：Python 3.11+、pytest 或 unittest、Python 标准库优先、JSON/JSONL、`tempfile`、`subprocess`、`pathlib`。不使用 LangChain/LangGraph、Docker/Kubernetes、云服务、数据库或大型 Agent SDK；不创建大量文件。临时目录是受控的练习工作区，不能宣称为完整安全沙箱。

练习案例使用 `sample_app/pricing.py` 中一个故意引入的折扣计算 Bug，以及与之对应的任务说明、`AGENTS.md` 和验收测试。

## 阶段总览

| 阶段 | 主题 | 关键问题 |
|---|---|---|
| Phase 1 | Context Engineering | Agent 需要哪些项目和任务上下文？ |
| Phase 2 | Execution + Verification | 修改如何在受控工作区中应用和被真实测试？ |
| Phase 3 | Feedback + Retry | 测试失败如何变成反馈并驱动下一次修改？ |
| Phase 4 | Policy Enforcement | 如何限制文件修改范围和允许执行的命令？ |
| Phase 5 | Human Approval + Change Lifecycle | 如何把人工批准绑定到确切的变更？ |
| Phase 6 | Observability + Evaluation + Interview | 如何追踪、评估并解释 Harness 的可靠性？ |

环境检查和创建 `harness-lab/` 是开始 Phase 1 前的准备步骤，不单独算一个学习 Phase。

## Phase 1 — Context Engineering

**目标：** 理解 Harness 如何为 Coding Agent 准备结构化、相关且有边界的上下文。

**实践内容：**

- 建立最小的 `sample_app/pricing.py`、任务说明、`AGENTS.md` 和验收测试。
- 定义 `ContextPackage`，由 Context Loader 加载任务描述、仓库指引、相关代码和验收要求。
- 定义 Mock Coding Agent 接口，让它接收并展示 Context Package；本阶段不要求它修改代码。

**验收：** Context Loader 真实读取文件；Mock Agent 收到正确的任务和相关代码；至少两个测试通过；展示实际 Context Package 和 ASCII 架构图。

**学习重点：** Harness 与 Agent 的职责、Context Engineering、`AGENTS.md`、Repository Structure、上下文选择，以及为什么更多 Context 不一定更好。说明 Harness Engineering 为什么超出 Prompt Engineering 的范围。

## Phase 2 — Execution + Verification

**目标：** 让 Harness 能在隔离的临时工作区应用一个候选改动，并用真实测试判断结果。

**实践内容：**

- 实现 Workspace Manager、候选变更的应用器、受限 Test Runner、`VerificationResult` 和初版 Verification Receipt。
- 用 `tempfile` 创建临时副本；只运行代码中明确配置的测试命令，使用 `subprocess` 且设置 timeout，不使用 `shell=True`。
- 本阶段仅处理练习任务指定的文件和命令；正式路径与命令策略在 Phase 4 完成。
- 本阶段不实现自动重试。

**验收：** 测试命令真实运行；Harness 根据退出码和测试结果记录 PASS/FAIL；原始示例项目没有被改动；超时结果能被明确识别。

**学习重点：** Execution Loop、Verification Loop、外部验证为什么比 Agent 自述可靠，以及 Verification Receipt 记录什么证据。

## Phase 3 — Feedback + Bounded Retry

**目标：** 让一次真实测试失败成为下一次修改的输入，而不是让 Harness 无条件替换成正确答案。

**实践内容：**

- 实现 Feedback Builder 和 Retry Controller。
- 第一次候选修改触发真实测试失败；Harness 收集相关错误和断言信息，构造反馈并交给 Mock Agent。
- Mock Agent 根据收到的失败反馈生成第二版候选；Harness 再次执行真实测试并生成最终 Receipt。
- 最大尝试次数为 3；每次记录候选、退出码、测试结果和重试原因。

**验收：** 展示第一次修改、失败证据、反馈内容、第二次修改、第二次真实测试结果和最终 Receipt。测试应确认第二次决策确实收到失败反馈；不得伪造 PASS 日志。

**学习重点：** Feedback Loop、Retry 与 Recovery 的区别、有限重试，以及为什么不能只依赖 Agent 的自我反思。

## Phase 4 — Policy Enforcement

**目标：** 用 Harness 外部规则约束文件修改和命令执行。

**实践内容：**

- 定义允许修改的目标文件和允许执行的测试命令。
- 使用路径解析与边界检查拒绝工作区外路径、`..` 路径穿越和符号链接越界。
- 命令只能从预先定义的 allowlist 选择；不把 Agent 提供的任意字符串直接传给 Shell。
- 非法路径和非法命令均以拒绝结果记录，采用 fail-closed 行为。

**验收：** 合法修改和允许命令可执行；至少一次越界写入和一次非法命令被拒绝；证明被拒绝操作没有产生工作区外副作用。

**学习重点：** Policy as Code、Least Privilege、Fail Closed、Prompt 指令与真正执行策略的差别，以及 Safety 与 Security 的边界。

## Phase 5 — Human Approval + Change Lifecycle

**目标：** 让受保护的最终工作区只接受经过验证并由人明确批准的变更。

**实践内容：**

- 实现 Change Review/Diff 和明确的执行状态：`PROPOSED` → `POLICY_CHECKED` → `VERIFIED` → `WAITING_APPROVAL` → `APPROVED`/`REJECTED` → `COMMITTED`。
- 审批绑定目标文件、具体 Diff、内容 Hash 和验证结果。
- 未批准不得应用到 Harness 管理的最终演示目录；审批后若内容改变，原审批失效。
- `COMMITTED` 只表示 Harness 应用到演示目标目录，不代表 Git Commit、Git Push 或发布。

**验收：** 合法改动经批准后应用；越界改动被拒绝；未批准不能应用；审批后替换内容会使旧批准失效；没有有效批准时副作用计数为零。

**学习重点：** Human-in-the-loop、Approval Binding、状态机与对话历史的区别、审批和执行的边界，以及临时目录、独立进程、容器、VM/MicroVM 的隔离取舍（仅作概念比较）。

## Phase 6 — Observability + Evaluation + Interview

**目标：** 用可追踪的运行证据和固定评测场景说明 Harness 的质量与局限。

**实践内容：**

- 实现 JSONL Trace Recorder，至少记录 `run_id`、`task_id`、`step`、`attempt`、`action`、`policy_decision`、`test_result`、`exit_code`、`duration_ms` 和 `final_status`。
- 生成 Execution Receipt，并能从 Trace 找到首次失败、重试原因、成功验证和策略拒绝。
- 实现以下 8 个评测场景：正常修改通过、失败后重试成功、重试耗尽、非法路径拒绝、未批准不能应用、命令超时、审批内容不一致、测试失败不得标记成功。
- 从真实测试和运行结果计算 Task Success Rate、Verification Pass Rate、Retry Recovery Rate、Policy Violation Count 和 Unauthorized Commit Count，并写清每个指标的分子与分母。
- 生成 `INTERVIEW_NOTES.md`，覆盖 Harness 定义、架构、Context、`AGENTS.md`、执行验证、反馈重试、策略审批、隔离、Observability 和 Evaluation；补充 10 道面试题、90 秒英文介绍、5 分钟 Demo 流程、对比图和生产扩展方向。

**验收：** 8 个场景均真实运行；指标由运行结果计算而不是手填；Fake Agent 结果和真实生产系统能力严格区分；Trace 可解释完整执行过程；面试材料指出本实验没有实现的生产能力。

**学习重点：** Observability 与 Evaluation 的区别、Agent 与 Harness 的责任边界、Harness 与 CI/CD/Sandbox 的关系，以及生产系统仍需的 OS 级隔离、Git/CI 集成、可复现环境、预算控制、分布式执行、审计和恢复能力。

## 每阶段固定教学与验收流程

每次只执行一个 Phase。阶段开始前先用简单中文说明目标、数据流和关键组件；只创建当前阶段必要的文件。完成后必须：

1. 运行真实程序和本阶段测试，展示命令、关键输出及 PASS/FAIL。
2. 展示实际输入、输出或 Trace；不得伪造运行结果。
3. 指出 2–3 个核心代码入口并解释调用关系。
4. 用简单中文讲解关键原理，给一个动手练习和两道面试题（含中文思路、英文参考回答及可能追问）。
5. 说明下一阶段的主题，然后停止，等待用户输入 `NEXT`。

控制指令：

- `NEXT`：开始下一阶段。
- `EXPLAIN`：只讲解当前实现，不改代码。
- `PRACTICE`：在当前阶段范围内增加动手练习。
- `INTERVIEW`：围绕当前阶段进行模拟面试。
- `REVIEW`：检查当前阶段代码和证据。
- `COMPARE`：结合已学的 Agent Engineering 对比当前 Harness 机制。

## 教学时必须守住的边界

- Harness 提供执行条件、施加策略、验证结果并管理任务生命周期；Agent 提出下一步行动或代码修改。
- Mock Agent 是确定性实验工具，不得把它的行为说成真实 LLM 能力。
- 测试通过只证明当前本地练习场景通过；临时目录不等于安全沙箱，不能据此宣称可安全运行任意生成代码。
- Harness 的审批不是自动 Git Commit、Push 或发布。没有用户明确指令，不做这些外部交付操作。
- 每个 Phase 未验收前不开始下一阶段；失败先修复和重新验证，不跳过。

## 最终学习目标

完成后，能够不看代码画出 Harness 架构，解释 Harness 与 Agent 的职责边界；讲清上下文、受限执行、外部验证、反馈重试、策略、人工审批、隔离、Trace 和 Evaluation；并用英文完成一个诚实说明实验范围及生产局限的技术面试介绍。
