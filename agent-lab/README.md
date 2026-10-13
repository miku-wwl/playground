# Mini Trading Support Agent — Phase 1

Phase 1 demonstrates an Agent loop with a scripted Fake Model. The model asks a real Python tool for a simulated balance, reads the tool result from message history, and then creates its final answer from that result.

No LLM or network request is used in this phase. The Ollama connection is reserved for Phase 2.

## Run

```powershell
python -m agent_lab
python -m pytest -q
```

## Project structure

```text
agent_lab/
  core/       AgentLoop and MessageHistory
  models/     decision types and FakeModelClient
  tools/      tool registry, dispatcher, and simulated balance tool
  __main__.py demo entry point
tests/        Agent loop tests
```

## Flow

```text
User request
    ↓
AgentLoop ── asks ──> FakeModelClient
    ↑                       │
    │                 ToolCall decision
    │                       ↓
Tool Result ← ToolDispatcher → ToolRegistry → get_my_balance()
    │
    └──── result is added to MessageHistory and sent to the model again
                               ↓
                         Final Answer
```

`max_steps` counts model decisions. A tool call is one step; the model's final answer is another.
