# AIG Hello World — agent development instructions

- This is an educational **consumer** of upstream Agentic Intent Gate v0.2.0, pinned to the exact Git commit in `pyproject.toml`.
- Keep startup easy: `uv run python main.py`. Do not re-introduce argparse/CLI commands without a request.
- Keep only four teaching files: root `main.py`, and `src/aig_hello/{planner,runtime,executor}.py`.
- Never simulate user Approval (`y`) or attest that a previous AIG process stopped without evidence/user instruction.
- AIG owns Plan validation, Approval binding, Authorization, durable claims and recovery. Do not bypass or copy these mechanisms.
- Do not rewrite stored identities, reset `.demo`, retry `Unknown` effects, expose capability tokens, or modify upstream AIG source.
- Use a fresh isolated test directory rather than the live `.demo` for automated tests.
- Do not commit/push/deploy unless explicitly asked.
