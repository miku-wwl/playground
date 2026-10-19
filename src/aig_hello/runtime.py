"""把 Hello World 的 Planner、Executor 和 AIG Runtime 连接起来。"""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from agentic_intent_gate.runtime import (
    ActionCommand,
    AdmissionCommand,
    ApprovalChoice,
    ApprovalDecisionRequest,
    BoundCapabilityAuthorization,
    CapabilityVerifier,
    ExecutableRegistry,
    Intent,
    ToolBinding,
    ToolCapability,
    open_runtime,
    provision_capability,
)

from aig_hello.executor import GreetingExecutor, provision_greeting_store
from aig_hello.planner import DeterministicHelloProvider

# AIG 只允许模型为这个工具提供一个非空的 message 字符串。
ARGUMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message"],
    "properties": {"message": {"type": "string", "minLength": 1, "maxLength": 256}},
}


def new_key():
    return str(uuid4())


def provision_if_missing(directory: Path) -> None:
    """首次初始化私有文件；存在时只复用，绝不重置旧身份和收据。"""
    directory = Path(directory).resolve()
    if directory.exists():
        if not directory.is_dir():
            raise ValueError("Data path is not a directory")
        if any(directory.iterdir()):
            needed = ("identity.json", "capability", "effects.sqlite3")
            if not all((directory / filename).is_file() for filename in needed):
                raise ValueError("Partial/unknown data directory: refusing to overwrite")
            return
    else:
        directory.mkdir(parents=True)

    # 六个固定身份字段定义了这个 Consumer 唯一允许执行的工具。
    binding = ToolBinding(
        "write_greeting", "1", "hello-sqlite", "hello-v1", "hello-world", str(uuid4())
    )
    provision_capability(directory / "capability")
    identity = directory / "identity.json"
    identity.write_text(json.dumps(vars(binding), sort_keys=True), encoding="utf-8")
    if os.name != "nt":
        os.chmod(identity, 0o600)
    provision_greeting_store(directory / "effects.sqlite3", binding)


@contextmanager
def open_hello_runtime(directory: Path, *, predecessor_stopped: bool):
    """通过 AIG v0.2.0 公共 API 注入 Planner、Tool、权限和持久化路径。"""
    directory = Path(directory).resolve()
    binding = ToolBinding(**json.loads((directory / "identity.json").read_text("utf-8")))
    executor = GreetingExecutor(directory / "effects.sqlite3", binding)
    verifier = CapabilityVerifier(
        (directory / "capability").read_text("ascii"),
        subject_id="hello-operator",
        binding=binding,
        operations=("read", "admit", "authorize", "execute"),
    )
    with open_runtime(
        gate_path=directory / "gate.sqlite3",
        provider=DeterministicHelloProvider(),  # 代替真实 LLM，只负责产生候选 Plan
        capability=ToolCapability(binding, "Write exactly one approved greeting", ARGUMENT_SCHEMA),
        registry=ExecutableRegistry(executor, binding=binding),
        verifier=verifier,
        policy=BoundCapabilityAuthorization(verifier, policy_revision="hello-policy-v1"),
        predecessor_stopped=predecessor_stopped,
    ) as runtime:
        # Token 不打印、不返回给 LLM。这里只提取 AIG 验证后的 Principal。
        header = "Bearer " + (directory / "capability").read_text("ascii")
        yield runtime, runtime.verifier.verify(header)


async def create_plan_run(runtime, message: str):
    """Plan 仅被生成、校验和持久化；不会直接执行 Tool。"""
    return await runtime.run_service.create(Intent(message))


def approve_or_reject(runtime, run, *, approve: bool):
    """审批与当前 Run 版本、完整 Plan 绑定。"""
    choice = ApprovalChoice.APPROVE if approve else ApprovalChoice.REJECT
    return runtime.run_service.decide(
        run.run_id, ApprovalDecisionRequest(choice, run.version)
    )


async def execute_approved(runtime, approved_run, principal):
    """AIG：Admission -> 独立 Authorization -> Durable Claim -> Executor。"""
    action = runtime.gateway.admit(
        AdmissionCommand(
            approved_run.run_id, approved_run.version, principal.subject_id, new_key()
        ),
        principal,
    ).action
    action = runtime.gateway.authorize(
        ActionCommand(action.action_id, action.version, new_key()), principal
    ).action
    return await runtime.gateway.execute(
        ActionCommand(action.action_id, action.version, new_key()), principal
    )
