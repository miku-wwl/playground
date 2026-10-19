"""Terminal demo: explicit approval is requested interactively, not fabricated."""

import argparse  # 标准库 argparse 负责把命令行文本解析成带属性的参数对象。
import asyncio  # 标准库 asyncio 提供运行 async 协程所需的事件循环。
import json  # 标准库 json 用于把 AIG Plan 和执行结果格式化为可读文本。
from pathlib import Path  # Path 提供跨平台的路径拼接和文件系统操作。

from aig_hello.adapters.executor import list_greetings  # Consumer 自己提供的只读收据查询函数。
from aig_hello.bootstrap.runtime_factory import open_hello_runtime, provision_if_missing  # Consumer 的 Runtime 组装与数据目录初始化。
from aig_hello.app.workflow import approve_or_reject, create_plan_run, execute_approved  # Consumer 对 AIG 生命周期的薄编排封装。


def parser() -> argparse.ArgumentParser:
    # 构造 CLI 参数解析器；这里只声明界面，不执行任何 Runtime 操作。
    p = argparse.ArgumentParser(description="Tiny AIG v0.2.0 Hello World consumer")  # 创建顶层解析器，并设置帮助信息中的项目描述。
    sub = p.add_subparsers(dest="command", required=True)  # 创建必选子命令组；解析结果会放在 args.command 属性中。
    run = sub.add_parser("run", help="Create Run, review Plan, approve/reject, execute")  # 定义 run：创建 Run、展示 Plan、审批并可能执行 Action。
    run.add_argument("--message", default="Hello from AIG!", help="1-256 chars")  # 接收用户意图文本；默认值也会成为最终 Plan 的 message 参数。
    run.add_argument("--data-dir", type=Path, default=Path(".demo"))  # 将数据目录转换成 Path，供初始化和 Runtime 打开持久化数据库。
    run.add_argument(
        "--predecessor-stopped", action="store_true", required=True,
        help="Operator attests no older process owns this demo store",  # 只有操作者明确声明前一个进程已停止，才允许使用该本地数据目录。
    )  # required=True 使安全声明成为必填参数，而不是隐式默认值。
    show = sub.add_parser("show", help="Read saved hello receipts (no execution)")  # 定义只读 show 命令，明确不会触发 Action。
    show.add_argument("--data-dir", type=Path, default=Path(".demo"))  # show 使用同样的数据目录定位 Consumer 的 effects.sqlite3。
    return p  # 返回完整解析器；真正解析参数由 main() 中的 parse_args() 完成。


async def run_demo(message: str, data_dir: Path, *, predecessor_stopped: bool) -> int:
    # 运行一次从 Intent（用户意图）到审批或执行结果的 CLI 演示。
    if not predecessor_stopped:  # 再次在业务入口检查安全声明，防止绕过 parser 直接调用此函数。
        raise ValueError("Explicit --predecessor-stopped confirmation required")  # 缺少明确声明时立即停止，绝不打开可能被其他进程占用的目录。
    provision_if_missing(data_dir)  # Consumer 首次运行时创建 identity、capability 和 effects 数据库；已有目录不会被覆盖。
    with open_hello_runtime(data_dir, predecessor_stopped=predecessor_stopped) as (
        runtime, principal
    ):  # 进入 Consumer 的 context manager；内部通过 AIG public API 打开 gate Runtime，并在离开时关闭资源。
        run = await create_plan_run(runtime, message)  # 把 message 传给 Consumer workflow；AIG RunService 随后生成、校验并持久化 Run/Plan。
        print(f"\n[1] Run: {run.run_id} | state={run.state.value} | version={run.version}")  # 展示 AIG 返回的 Run 标识、状态和乐观版本号。
        if run.plan is None:  # 没有有效 Plan 表示 AIG 在审批前已拒绝该 Intent，不能继续进入副作用流程。
            print("Plan rejected before approval; inspect the intent and validation rules.")  # 给操作者提示：问题发生在 Plan 验证阶段。
            return 1  # 以非零状态结束，表示没有可供审批的计划。
        print("\n[2] PROPOSED PLAN (not executed):")  # 明确提示当前只是待审批提案，还没有执行工具。
        print(json.dumps(run.plan.to_dict(), indent=2, ensure_ascii=False))  # 将 AIG Plan 转成字典并格式化打印，让操作者核对精确参数。
        if run.state.value != "AwaitingApproval":  # 只有 AIG 明确进入待审批状态才允许显示审批问题。
            print(f"Not awaiting approval (state={run.state.value}). No action executed.")  # 其他状态都不应被 CLI 当作可执行状态。
            return 1  # 防止绕过 Approval（人工审批）而创建或执行 Action。

        # 这里不设置隐式 YES；操作者必须针对屏幕上显示的这个精确 Plan 作出决定。
        answer = input("\n[3] Approve this exact Plan? [y/N]: ").strip().lower()  # 阻塞等待输入；y/yes 表示同意，n、Enter 或其他文本均不批准。
        approved = answer in {"y", "yes"}  # 把用户输入转换成布尔值，后续只把 True 交给 Approval workflow。
        decided = approve_or_reject(runtime, run, approve=approved)  # 调用 Consumer workflow，由 AIG RunService 持久化 APPROVE 或 REJECT 决定及精确 Plan 绑定。
        print(f"    Decision: {decided.state.value} | version={decided.version}")  # 输出 AIG 决定后的 Run 状态和递增版本号。
        if not approved:  # n、Enter 或其他非 y/yes 输入都走安全停止分支。
            print("[4] Stopped safely; NO greeting was written.")  # 明确告诉操作者拒绝不会创建 Greeting 副作用。
            return 0  # 拒绝是一次正常、已处理的用户选择，因此使用成功退出码。

        print("\n[4] Action Admission -> independent Authorization -> Execution")  # 说明批准后仍有独立的 Admission 和 Authorization 闸门。
        result = await execute_approved(runtime, decided, principal)  # Consumer workflow 依次调用 AIG gateway.admit、authorize、execute，最终才会进入 ToolExecutor。
        action = result.action  # 取出 AIG 返回的 Action（受控执行对象），其中包含状态、effect key 和结果。
        print(f"    Action: {action.action_id}")  # 输出 Action 标识，便于和 AIG gate 数据库中的记录对应。
        print(f"    State:  {action.state.value}")  # 输出最终状态；只有 Succeeded 才代表执行结果得到确认。
        print(f"    Effect: {action.effect_key}")  # 输出 AIG 为本次副作用分配的幂等 effect key。
        print("    Result: " + json.dumps(dict(action.result or {}), ensure_ascii=False))  # 将 ToolExecutor 返回的 receipt 等结果安全地格式化输出。
        if action.state.value != "Succeeded":  # Unknown 或其他非成功状态不能被 CLI 当作已完成。
            print("    Not confirmed; do NOT blindly retry this Action.")  # 提醒操作者未知结果可能已经产生副作用，不能盲目重试。
            return 1  # 非确认状态以非零退出，要求外部人工调查而不是自动补偿。

    print("\n[5] Saved greeting receipt (read-only view):")  # Runtime 关闭后，进入 Consumer 自己的只读收据展示阶段。
    for text, receipt, _ in list_greetings(data_dir / "effects.sqlite3"):  # 读取 Consumer effects 数据库；下划线丢弃不需要显示的 effect key。
        print(f"    {text!r} | receipt={receipt}")  # 输出已确认 greeting 和 receipt，不执行任何新的 AIG Action。
    print("\nNext: uv run aig-hello show --data-dir .demo")  # 提供后续只读查询命令，方便再次查看持久化收据。
    return 0  # 到达这里代表审批、授权、执行和结果确认均成功。


def main() -> None:
    # CLI 入口；由 pyproject.toml 的 aig-hello 脚本映射到这里。
    args = parser().parse_args()  # 解析 sys.argv，并生成带 command、message、data_dir 等属性的 Namespace。
    if args.command == "show":  # show 是纯读取分支，不初始化 AIG Runtime，也不可能执行副作用。
        rows = list_greetings(args.data_dir / "effects.sqlite3")  # 从 Consumer 数据库读取所有已确认 greeting 行。
        if not rows:  # 空结果表示目前没有成功持久化的 receipt。
            print("No confirmed greeting receipts yet.")  # 向用户明确报告当前没有可展示的成功效果。
        for i, (message, receipt, effect_key) in enumerate(rows, 1):  # 为每条收据生成从 1 开始的展示序号并解包记录字段。
            print(f"{i}. {message} | receipt={receipt} | effect_key={effect_key}")  # 展示消息、receipt 和幂等 key，但不触发执行。
        return  # show 分支完成后直接返回，避免落入 run 分支。
    try:  # 仅把预期的本地输入、路径和 EOF 错误转换为友好的 CLI 输出。
        code = asyncio.run(  # 创建并运行事件循环，等待 async run_demo 完成后取得整数退出码。
            run_demo(args.message, args.data_dir,
                     predecessor_stopped=args.predecessor_stopped)
        )  # run_demo 内部的 await 会在此事件循环中驱动 AIG 的异步 Run/Execution 流程。
    except (OSError, ValueError, EOFError) as exc:  # 捕获文件系统、显式参数校验和输入流结束等预期错误。
        print(f"Demo stopped: {exc}")  # 输出错误原因，但不伪造成功或执行结果。
        raise SystemExit(2) from None  # 用退出码 2 表示 CLI 使用或运行环境错误，并隐藏无用的异常链。
    raise SystemExit(code)  # 将 run_demo 的业务结果转换成操作系统可见的进程退出码。


if __name__ == "__main__":  # 只有直接执行此文件时才进入 CLI；被导入测试时不会自动运行。
    main()  # 启动命令行入口，脚本入口和 python -m 场景都共享同一实现。
