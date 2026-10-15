# Acceptance criteria for the later pricing fix

These are requirements for the task. Phase 1 loads them as context but does not run them.

1. `apply_discount(100.00, 20)` returns `80.00`.
2. `apply_discount(50.00, 0)` returns `50.00`.

The first case currently fails because the example implementation adds the percentage instead of subtracting it. The failure will be exercised by the real test runner in a later phase.
