# Agent notes for this small Consumer

This is **not** the Agentic Intent Gate core repository. Never reimplement AIG's
Approval, Authorization, Action Gateway, CAS, claim, or recovery logic here.

- Install AIG at the exact full Git commit pinned by `pyproject.toml`.
- Integrate ONLY through `agentic_intent_gate.runtime` public imports.
- The planner is deterministic and makes no actual model call.
- Preserve the `app/`, `adapters/`, `bootstrap/` responsibilities and `aig_hello.app.cli:main` entrypoint.
- Do not mistake the CLI's interactive approval for production authentication.
- Keep `hello-world`/`write_greeting`/scope and the private effect-store identity stable.
- Never overwrite a preexisting data directory or regenerate its token/scope on restart.
- No real external APIs, secrets, background retries, dynamic tools, or production traffic.
- Do not change AIG's core code or the v0.2.0 release tag.
- Execute mutation commands only with clear user authorization; never commit/push automatically.
