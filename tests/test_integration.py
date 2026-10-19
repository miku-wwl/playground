"""Real Runtime tests: require installed AIG v0.2.0 dependency."""

import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from agentic_intent_gate.runtime import (
    ActionCommand, AdmissionCommand, AttemptContext, ExecutionSpec,
    EXTERNAL_PAYLOAD_REVISION, Outcome,
)
from uuid import uuid4

from aig_hello.executor import GreetingExecutor, list_greetings
from aig_hello.runtime import (
    open_hello_runtime, provision_if_missing,
    approve_or_reject,
    create_plan_run,
    execute_approved,
    new_key,
)


class HelloAIGIntegrationTests(unittest.TestCase):
    def test_approved_plan_executes_once_with_durable_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            provision_if_missing(directory)
            with open_hello_runtime(directory, predecessor_stopped=True) as (runtime, principal):
                run = asyncio.run(create_plan_run(runtime, "Hello test!"))
                self.assertEqual(run.state.value, "AwaitingApproval")
                self.assertEqual(run.version, 4)
                self.assertEqual(run.plan.steps[0].arguments["message"], "Hello test!")
                decided = approve_or_reject(runtime, run, approve=True)
                self.assertEqual(decided.state.value, "Approved")
                result = asyncio.run(execute_approved(runtime, decided, principal))
                self.assertEqual(result.action.state.value, "Succeeded")
                receipt = result.action.result["receipt_reference"]
                self.assertEqual(len(list_greetings(directory / "effects.sqlite3")), 1)
                self.assertEqual(list_greetings(directory / "effects.sqlite3")[0][1], receipt)
            # Persistence survives closing and reopening the AIG runtime.
            with open_hello_runtime(directory, predecessor_stopped=True) as (runtime, _):
                self.assertIsNotNone(runtime.actions.get(result.action.action_id))
            self.assertEqual(len(list_greetings(directory / "effects.sqlite3")), 1)

    def test_executor_deduplicates_the_exact_same_effect_key(self):
        async def probe(directory):
            import json
            from agentic_intent_gate.runtime import ToolBinding
            binding = ToolBinding(**json.loads((directory / "identity.json").read_text()))
            spec = ExecutionSpec(
                "write_greeting", "1", "hello-world", {"message": "repeat"},
                "hello-sqlite", "hello-v1", binding.execution_scope,
                EXTERNAL_PAYLOAD_REVISION,
            )
            executor = GreetingExecutor(directory / "effects.sqlite3", binding)
            key = str(uuid4())
            loop = asyncio.get_running_loop()
            context = AttemptContext(str(uuid4()), loop.time() + 5, asyncio.Event())
            first = await executor.execute(spec, key, context)
            second = await executor.execute(spec, key, context)
            return first, second

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            provision_if_missing(directory)
            first, second = asyncio.run(probe(directory))
            self.assertEqual(first.category, Outcome.SUCCESS)
            self.assertEqual(second.category, Outcome.SUCCESS)
            self.assertEqual(first.receipt_reference, second.receipt_reference)
            self.assertEqual(len(list_greetings(directory / "effects.sqlite3")), 1)

    def test_rejection_causes_no_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            provision_if_missing(directory)
            with open_hello_runtime(directory, predecessor_stopped=True) as (runtime, principal):
                run = asyncio.run(create_plan_run(runtime, "No thanks"))
                rejected = approve_or_reject(runtime, run, approve=False)
                self.assertEqual(rejected.state.value, "Rejected")
                with self.assertRaises(Exception):
                    runtime.gateway.admit(
                        AdmissionCommand(rejected.run_id, rejected.version,
                                         principal.subject_id, new_key()),
                        principal,
                    )
                self.assertEqual(list_greetings(directory / "effects.sqlite3"), [])

    def test_approval_alone_does_not_authorize_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            provision_if_missing(directory)
            with open_hello_runtime(directory, predecessor_stopped=True) as (runtime, principal):
                run = asyncio.run(create_plan_run(runtime, "Approval isn't authorization"))
                decided = approve_or_reject(runtime, run, approve=True)
                action = runtime.gateway.admit(
                    AdmissionCommand(decided.run_id, decided.version,
                                     principal.subject_id, new_key()), principal,
                ).action
                self.assertEqual(action.state.value, "Pending")
                with self.assertRaises(Exception):
                    asyncio.run(runtime.gateway.execute(
                        ActionCommand(action.action_id, action.version, new_key()), principal
                    ))
                with closing(sqlite3.connect(directory / "effects.sqlite3")) as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM greetings").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
