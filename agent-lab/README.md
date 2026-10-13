# Mini Trading Support Agent — Phase 2

The app runs a real local Ollama model. A deterministic Fake Model remains available to unit tests so the Agent loop can be tested without model calls.

The Ollama client sends the conversation to `POST /api/chat` and asks for a decision matching a JSON Schema. Python validates the response, then the Agent either dispatches an allowed tool or returns the model's final answer. Tool data remains simulated in memory.

## Run

```powershell
# Run the local Ollama demos
python -m agent_lab --scenario balance
python -m agent_lab --scenario order
python -m agent_lab --scenario unsupported

# Tests use the Fake Model and do not call Ollama
python -m pytest -q
```

The default model is `phi4-mini:latest`; select another installed model with `--model-name`.

## Project structure

```text
agent_lab/
  core/       AgentLoop and MessageHistory
  models/     decision types, FakeModelClient, and OllamaModelClient
  tools/      tool registry, dispatcher, and simulated read-only tools
  __main__.py demo entry point
tests/        Agent loop tests
```

## Flow

```text
User request → AgentLoop → OllamaModelClient → Ollama HTTP API
                    ↑            │ JSON decision
                    │            ↓
Tool result ← ToolDispatcher → ToolRegistry → Python tool
     │
     └── added to history and sent back to Ollama for the final answer
```

`max_steps` counts model decisions. A tool call is one step; the model's final answer is another.
The Phase 2 demo covers a balance lookup, an order lookup, and an unsupported question. Approval and the Phase 3 security tests are not part of this phase.
