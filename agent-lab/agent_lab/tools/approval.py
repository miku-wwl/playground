import json
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4


PENDING_APPROVAL = "PENDING_APPROVAL"


class ApprovalStateError(ValueError):
    """The approval request is missing or is no longer pending."""


@dataclass
class _ApprovalRecord:
    approval_id: str
    tool_name: str
    arguments_json: str
    authenticated_user_id: str
    status: str = PENDING_APPROVAL
    decided_by: str | None = None
    result: object | None = None

    def public_view(self) -> dict[str, object]:
        return {
            "approval_id": self.approval_id,
            "status": self.status,
            "tool_name": self.tool_name,
            "arguments": json.loads(self.arguments_json),
            "authenticated_user_id": self.authenticated_user_id,
            "decided_by": self.decided_by,
            "result": self.result,
        }


class ApprovalStore:
    """Keeps exact, in-memory approval requests for this demo process."""

    def __init__(self) -> None:
        self._records: dict[str, _ApprovalRecord] = {}
        self._lock = Lock()

    def create(
        self,
        tool_name: str,
        arguments: dict[str, object],
        authenticated_user_id: str,
    ) -> dict[str, object]:
        record = _ApprovalRecord(
            approval_id=f"APR-{uuid4().hex[:12]}",
            tool_name=tool_name,
            arguments_json=json.dumps(arguments, sort_keys=True, separators=(",", ":")),
            authenticated_user_id=authenticated_user_id,
        )
        with self._lock:
            self._records[record.approval_id] = record
        return record.public_view()

    def pending(self) -> list[dict[str, object]]:
        with self._lock:
            return [
                record.public_view()
                for record in self._records.values()
                if record.status == PENDING_APPROVAL
            ]

    def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        approver_id: str,
    ) -> dict[str, object]:
        with self._lock:
            record = self._get_pending(approval_id)
            record.status = "APPROVED" if approved else "REJECTED"
            record.decided_by = approver_id
            return record.public_view()

    def mark_executed(self, approval_id: str, result: object) -> None:
        with self._lock:
            record = self._get_with_status(approval_id, "APPROVED")
            record.status = "EXECUTED"
            record.result = result

    def mark_failed(self, approval_id: str, error: str) -> None:
        with self._lock:
            record = self._get_with_status(approval_id, "APPROVED")
            record.status = "FAILED"
            record.result = {"error": error}

    def _get_pending(self, approval_id: str) -> _ApprovalRecord:
        record = self._records.get(approval_id)
        if record is None or record.status != PENDING_APPROVAL:
            raise ApprovalStateError(
                f"Approval request is missing or not pending: {approval_id}"
            )
        return record

    def _get_with_status(self, approval_id: str, expected_status: str) -> _ApprovalRecord:
        record = self._records.get(approval_id)
        if record is None or record.status != expected_status:
            raise ApprovalStateError(
                f"Approval request {approval_id} must be {expected_status}"
            )
        return record
