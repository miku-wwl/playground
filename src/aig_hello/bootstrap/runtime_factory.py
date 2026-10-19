"""Composition root: wire the EXTERNAL app to AIG's supported PUBLIC API."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from agentic_intent_gate.runtime import (
    BoundCapabilityAuthorization,
    CapabilityVerifier,
    ExecutableRegistry,
    ToolBinding,
    ToolCapability,
    open_runtime,
    provision_capability,
)

from aig_hello.adapters.executor import GreetingExecutor, provision_greeting_store
from aig_hello.adapters.planner import DeterministicHelloProvider

ARGUMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message"],
    "properties": {
        "message": {"type": "string", "minLength": 1, "maxLength": 256},
    },
}


def make_binding(scope: str):
    return ToolBinding(
        "write_greeting", "1", "hello-sqlite", "hello-v1", "hello-world", scope
    )


def provision_if_missing(directory: Path) -> None:
    """Provision only on first use. Reuse the SAME identity across restarts."""
    directory = Path(directory).resolve()
    if directory.exists():
        if not directory.is_dir():
            raise ValueError("Data path is not a directory")
        if any(directory.iterdir()):
            # Existing state must already be a complete, previously provisioned set.
            if not all((directory / name).is_file() for name in
                       ("identity.json", "capability", "effects.sqlite3")):
                raise ValueError("Partial/unknown data directory: refusing to overwrite it")
            return
    else:
        directory.mkdir(parents=True)

    binding = make_binding(str(uuid4()))
    provision_capability(directory / "capability")
    identity_file = directory / "identity.json"
    identity_file.write_text(json.dumps(vars(binding), sort_keys=True), encoding="utf-8")
    if os.name != "nt":
        os.chmod(identity_file, 0o600)
    provision_greeting_store(directory / "effects.sqlite3", binding)


@contextmanager
def open_hello_runtime(directory: Path, *, predecessor_stopped: bool):
    """Never lie about the single-owner predecessor check."""
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
        provider=DeterministicHelloProvider(),
        capability=ToolCapability(binding, "Write exactly one approved greeting", ARGUMENT_SCHEMA),
        registry=ExecutableRegistry(executor, binding=binding),
        verifier=verifier,
        policy=BoundCapabilityAuthorization(verifier, policy_revision="hello-policy-v1"),
        predecessor_stopped=predecessor_stopped,
    ) as runtime:
        # Token is used only locally and never printed or persisted in source/logs.
        header = "Bearer " + (directory / "capability").read_text("ascii")
        yield runtime, runtime.verifier.verify(header)
