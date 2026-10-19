"""One complete AIG lifecycle: Intent -> Run -> Approval -> Action -> Receipt."""

from uuid import uuid4

from agentic_intent_gate.runtime import (
    ActionCommand,
    AdmissionCommand,
    ApprovalChoice,
    ApprovalDecisionRequest,
    Intent,
)


def new_key() -> str:
    return str(uuid4())


async def create_plan_run(runtime, message: str):
    """The generated proposal is stored as an AIG Run, not automatically executed."""
    return await runtime.run_service.create(Intent(message))


def approve_or_reject(runtime, run, *, approve: bool):
    choice = ApprovalChoice.APPROVE if approve else ApprovalChoice.REJECT
    return runtime.run_service.decide(
        run.run_id, ApprovalDecisionRequest(choice, run.version)
    )


async def execute_approved(runtime, approved_run, principal):
    """Action can be executed only after an exact Plan approval and separate grant."""
    admitted = runtime.gateway.admit(
        AdmissionCommand(
            approved_run.run_id,
            approved_run.version,
            principal.subject_id,
            new_key(),
        ),
        principal,
    ).action
    authorized = runtime.gateway.authorize(
        ActionCommand(admitted.action_id, admitted.version, new_key()), principal
    ).action
    command = ActionCommand(authorized.action_id, authorized.version, new_key())
    return await runtime.gateway.execute(command, principal)
