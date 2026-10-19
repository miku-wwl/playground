"""Host-owned ToolExecutor: exactly one durable SQLite greeting per effect_key.

This is a local learning-only example, NOT a general exactly-once remote API protocol.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from agentic_intent_gate.runtime import (
    EXTERNAL_PAYLOAD_REVISION,
    Outcome,
    ToolOutcome,
)


def binding_json(binding) -> str:
    """Stable trusted identity for the separate effect store."""
    return json.dumps(asdict(binding), sort_keys=True, separators=(",", ":"))


def provision_greeting_store(path: Path, binding) -> None:
    """Create a brand-new store; never silently reset or repurpose an existing one."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Effect store already exists: {path}")
    # Exclusive create protects the operator from wiping an existing database.
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(path)) as db:
        db.executescript(
            """
            CREATE TABLE identity (
              singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
              binding TEXT NOT NULL
            ) STRICT;
            CREATE TABLE greetings (
              effect_key TEXT PRIMARY KEY,
              payload_digest TEXT NOT NULL,
              receipt TEXT UNIQUE NOT NULL,
              message TEXT NOT NULL
            ) STRICT;
            """
        )
        db.execute("INSERT INTO identity(singleton, binding) VALUES (1, ?)",
                   (binding_json(binding),))
        db.commit()


class GreetingExecutor:
    def __init__(self, store_path: Path, binding):
        self.store_path = Path(store_path)
        self.binding = binding

    async def execute(self, spec, effect_key, context):
        """AIG invokes this only after approval, authorization, and durable claim.

        Still independently check identity/arguments: defense in depth.
        """
        def result(category, *, receipt=None, no_effect_reason=None):
            return ToolOutcome(
                category,
                effect_key,
                spec.execution_scope,
                spec.target,
                spec.payload_digest(),
                receipt,
                no_effect_reason,
            )

        args = dict(spec.arguments)
        if (
            not self.binding.matches(spec)
            or spec.identity_revision != EXTERNAL_PAYLOAD_REVISION
            or set(args) != {"message"}
            or type(args["message"]) is not str
            or not 1 <= len(args["message"]) <= 256
            or len(args["message"].encode("utf-8")) > 1024
        ):
            return result(Outcome.CONFIRMED_FAILURE, no_effect_reason="INPUT_REJECTED")

        try:
            if str(UUID(effect_key, version=4)) != effect_key:
                return result(Outcome.CONFIRMED_FAILURE, no_effect_reason="INPUT_REJECTED")
            if context.expired():
                return ToolOutcome(Outcome.UNKNOWN_OUTCOME)

            # SQLite URI mode=rw means an absent effect store is NOT created implicitly.
            uri = self.store_path.resolve().as_uri() + "?mode=rw"
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT binding FROM identity WHERE singleton=1").fetchone()
                if row != (binding_json(self.binding),):
                    return result(Outcome.CONFIRMED_FAILURE,
                                  no_effect_reason="STORE_IDENTITY_MISMATCH")

                digest = spec.payload_digest()
                old = db.execute(
                    "SELECT payload_digest, receipt, message FROM greetings WHERE effect_key=?",
                    (effect_key,),
                ).fetchone()
                if old is not None:
                    if old[0] != digest:
                        return result(Outcome.CONFIRMED_FAILURE,
                                      no_effect_reason="PAYLOAD_CONFLICT")
                    if old[2] != args["message"]:
                        return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
                    return result(Outcome.SUCCESS, receipt=old[1])

                # Both the effect and its evidence are committed in one transaction.
                receipt = str(uuid4())
                db.execute(
                    "INSERT INTO greetings(effect_key, payload_digest, receipt, message)"
                    " VALUES (?, ?, ?, ?)",
                    (effect_key, digest, receipt, args["message"]),
                )
                if context.expired():
                    return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
                db.commit()
                if context.expired():
                    return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
                return result(Outcome.SUCCESS, receipt=receipt)
        except (sqlite3.Error, OSError, ValueError, UnicodeError):
            # A commit exception may mean it happened. Never infer no effect.
            return ToolOutcome(Outcome.UNKNOWN_OUTCOME)


def list_greetings(path: Path) -> list[tuple[str, str, str]]:
    """Read-only inspection; does not dispatch any AIG Action."""
    if not Path(path).is_file():
        return []
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        return db.execute(
            "SELECT message, receipt, effect_key FROM greetings ORDER BY rowid"
        ).fetchall()
