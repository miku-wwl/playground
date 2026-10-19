"""AIG Hello World：只需运行 uv run python main.py。没有 argparse / 子命令。"""

import asyncio
import json
from pathlib import Path

from aig_hello.executor import list_greetings
from aig_hello.runtime import (
    approve_or_reject,
    create_plan_run,
    execute_approved,
    open_hello_runtime,
    provision_if_missing,
)

# 需要改消息时，只改这一行；运行数据固定在项目根目录 .demo。
MESSAGE = "Hello from AIG!"
DATA_DIR = Path(__file__).resolve().parent / ".demo"


async def run_demo(message: str = MESSAGE, data_dir: Path = DATA_DIR) -> None:
    """按顺序展示 Intent -> Plan -> Approval -> Authorization -> Tool。"""
    data_dir = Path(data_dir)
    if data_dir.exists():
        # AIG 使用 single-owner 约束；重复运行时需要你确认旧进程已停止。
        answer = input("确认之前使用此数据目录的进程已全部停止？[y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("已取消；没有启动 Runtime，也没有做出审批决定。")
            return

    provision_if_missing(data_dir)
    with open_hello_runtime(data_dir, predecessor_stopped=True) as (runtime, principal):
        # 这里由确定性 Provider 生成 JSON，AIG 验证并写入 Run 数据库。
        run = await create_plan_run(runtime, message)
        print(f"\n[1] Run: {run.run_id} | {run.state.value} | version={run.version}")
        if run.plan is None or run.state.value != "AwaitingApproval":
            print("没有可审批的有效 Plan，未执行工具。")
            return

        print("\n[2] Plan（仅提议，尚未执行 Tool）:")
        print(json.dumps(run.plan.to_dict(), indent=2, ensure_ascii=False))
        decision = input("\n[3] 是否批准这个准确的 Plan？[y/n]: ").strip().lower()
        if decision not in {"y", "yes", "n", "no"}:
            # 没有明确回答时，不能代替用户在数据库里写入 REJECT。
            print("未收到明确决定；Run 保持 AwaitingApproval，未执行工具。")
            return

        approved = decision in {"y", "yes"}
        decided = approve_or_reject(runtime, run, approve=approved)
        print(f"[4] 审批结果：{decided.state.value}")
        if not approved:
            print("已拒绝，未执行工具。")
            return

        # 人工批准仅是第一关；AIG 还要 Admission、独立 Authorization 和持久化 Claim。
        result = await execute_approved(runtime, decided, principal)
        action = result.action
        print(f"[5] Action: {action.action_id} | state={action.state.value}")
        print("    Result:", json.dumps(dict(action.result or {}), ensure_ascii=False))
        if action.state.value != "Succeeded":
            print("执行结果尚未确认；不要盲目重试。")
            return

    # 执行成功后，只读查看 Consumer 独立 SQLite 数据库里的 Receipt。
    print("\n[6] 保存的 Greeting / Receipt:")
    for greeting, receipt, _ in list_greetings(data_dir / "effects.sqlite3"):
        print(f"    {greeting} | receipt={receipt}")


if __name__ == "__main__":
    asyncio.run(run_demo())
