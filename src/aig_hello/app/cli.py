"""Terminal demo: explicit approval is requested interactively, not fabricated."""

import argparse
import asyncio
import json
from pathlib import Path

from aig_hello.adapters.executor import list_greetings
from aig_hello.bootstrap.runtime_factory import open_hello_runtime, provision_if_missing
from aig_hello.app.workflow import approve_or_reject, create_plan_run, execute_approved


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Tiny AIG v0.2.0 Hello World consumer")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Create Run, review Plan, approve/reject, execute")
    run.add_argument("--message", default="Hello from AIG!", help="1-256 chars")
    run.add_argument("--data-dir", type=Path, default=Path(".demo"))
    run.add_argument(
        "--predecessor-stopped", action="store_true", required=True,
        help="Operator attests no older process owns this demo store",
    )
    show = sub.add_parser("show", help="Read saved hello receipts (no execution)")
    show.add_argument("--data-dir", type=Path, default=Path(".demo"))
    return p


async def run_demo(message: str, data_dir: Path, *, predecessor_stopped: bool) -> int:
    if not predecessor_stopped:
        raise ValueError("Explicit --predecessor-stopped confirmation required")
    provision_if_missing(data_dir)
    with open_hello_runtime(data_dir, predecessor_stopped=predecessor_stopped) as (
        runtime, principal
    ):
        run = await create_plan_run(runtime, message)
        print(f"\n[1] Run: {run.run_id} | state={run.state.value} | version={run.version}")
        if run.plan is None:
            print("Plan rejected before approval; inspect the intent and validation rules.")
            return 1
        print("\n[2] PROPOSED PLAN (not executed):")
        print(json.dumps(run.plan.to_dict(), indent=2, ensure_ascii=False))
        if run.state.value != "AwaitingApproval":
            print(f"Not awaiting approval (state={run.state.value}). No action executed.")
            return 1

        # IMPORTANT: no implicit YES. One visible decision for THIS exact Plan.
        answer = input("\n[3] Approve this exact Plan? [y/N]: ").strip().lower()
        approved = answer in {"y", "yes"}
        decided = approve_or_reject(runtime, run, approve=approved)
        print(f"    Decision: {decided.state.value} | version={decided.version}")
        if not approved:
            print("[4] Stopped safely; NO greeting was written.")
            return 0

        print("\n[4] Action Admission -> independent Authorization -> Execution")
        result = await execute_approved(runtime, decided, principal)
        action = result.action
        print(f"    Action: {action.action_id}")
        print(f"    State:  {action.state.value}")
        print(f"    Effect: {action.effect_key}")
        print("    Result: " + json.dumps(dict(action.result or {}), ensure_ascii=False))
        if action.state.value != "Succeeded":
            print("    Not confirmed; do NOT blindly retry this Action.")
            return 1

    print("\n[5] Saved greeting receipt (read-only view):")
    for text, receipt, _ in list_greetings(data_dir / "effects.sqlite3"):
        print(f"    {text!r} | receipt={receipt}")
    print("\nNext: uv run aig-hello show --data-dir .demo")
    return 0


def main() -> None:
    args = parser().parse_args()
    if args.command == "show":
        rows = list_greetings(args.data_dir / "effects.sqlite3")
        if not rows:
            print("No confirmed greeting receipts yet.")
        for i, (message, receipt, effect_key) in enumerate(rows, 1):
            print(f"{i}. {message} | receipt={receipt} | effect_key={effect_key}")
        return
    try:
        code = asyncio.run(
            run_demo(args.message, args.data_dir,
                     predecessor_stopped=args.predecessor_stopped)
        )
    except (OSError, ValueError, EOFError) as exc:
        print(f"Demo stopped: {exc}")
        raise SystemExit(2) from None
    raise SystemExit(code)


if __name__ == "__main__":
    main()
