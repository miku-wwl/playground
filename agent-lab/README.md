# Mini Trading Support Agent — Phase 3

This local learning project demonstrates an Agent that proposes tool calls through Ollama, while Python validates, authorizes, and executes them. Phase 3 adds argument schemas, runtime user scoping, execution limits, and human approval for simulated support-ticket creation.

All balances, orders, and tickets are in-memory demo data. The CLI supplies `user-123` as its runtime identity; this is not a real authentication system. Approval records live only for the current process.

## Run

```powershell
python -m agent_lab --scenario balance
python -m agent_lab --scenario order
python -m agent_lab --scenario unsupported

# Real Ollama proposes a ticket; type APPROVE or REJECT
python -m agent_lab --scenario support-ticket

# Deterministic security demos; these do not call Ollama
python -m agent_lab.phase3_demo prompt-injection
python -m agent_lab.phase3_demo ticket-approval

# Tests use scripted models and simulated tools
python -m pytest -q

# Phase 4 deterministic evaluation: six scripted scenarios
python -m agent_lab.evaluation.runner --mode fake

# Phase 4 live evaluation: five local Ollama scenarios, reported separately
python -m agent_lab.evaluation.runner --mode ollama --model-name phi4-mini:latest
```

The default model is `phi4-mini:latest`; choose another installed model with `--model-name`. The Agent, model calls, and tool calls all have limits.

## Project structure

```text
agent_lab/
  core/       AgentLoop and MessageHistory
  models/     decision types, Fake Model, and Ollama client
  tools/      schemas, registry, dispatcher, approval state, demo tools
  evaluation/ JSONL trace writer and evaluation runner
  phase3_demo.py
  __main__.py
tests/        Agent-loop, Ollama protocol, security, and evaluation tests
docs/         Phase 3 and Phase 4 reports and learning guides
```

See the [Phase 3 acceptance report](docs/PHASE3_ACCEPTANCE_REPORT.md) and [learning guide](docs/PHASE3_LEARNING_GUIDE.md), the [Phase 4 acceptance report](docs/PHASE4_ACCEPTANCE_REPORT.md) and [learning guide](docs/PHASE4_LEARNING_GUIDE.md), and the [final interview cheat sheet](docs/INTERVIEW-CHEATSHEET.md).
