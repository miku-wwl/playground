# Chat Handoff — Aeron Match Replay Lab

Updated: 2026-10-14

## Current checkout

- Workspace: `D:\workshop\oct\playground\aeron-match-replay-lab`
- Branch: `main`
- Phase 0 commit pushed to GitHub: `9e2e278318662c18fe17f5c92e3c7a4470cd5c22`
- Phase 1 implementation and handoff notes pushed to GitHub as `d3f4e93f4ef8c5b684892eb7deb4b43c3c1c9720`; local, tracking, and live remote SHAs matched after push.
- No repository `AGENTS.md`, README, prior planning file, or prior handoff file was present when this note was created.

## Java source layout

```text
src/main/java/dev/playground/replaylab/
  AeronMatchReplayLabApplication.java
  controller/TradingReplayDemo.java
  service/ReplayService.java
  gateway/AeronArchiveGateway.java
  codec/TradingEventCodec.java
  model/TradingEvent.java
  model/TradingState.java
  phase3/Phase3ArchiveProcess.java
  phase3/Phase3PublisherProcess.java
  phase3/Phase3ConsumerProcess.java
  phase3/Phase3ProcessSupport.java

src/test/java/dev/playground/replaylab/
  service/AeronArchiveRoundTripTest.java
  model/TradingStateTest.java
```

The Spring Boot application class stays in the root package so component scanning includes the subpackages.

## User-supplied architecture update

The learning story is now a latency-sensitive upstream publisher, Aeron transport and Archive recording, and an independently restartable downstream consumer that replays missed events and catches up with the live stream. Treat this as a simplified learning hypothesis; do not claim the user's OKX team had these exact processes or downstream workloads.

The most important Phase 3 change is from a single-process reset/replay demo to three independent Java processes: publisher, Archive plus its MediaDriver, and consumer. The publisher continues while the consumer is stopped; the restarted consumer recovers from a recording/checkpoint, replays missed events, transitions to live, and verifies its resulting projection.

## Preserved progress

- Phase 0: PASS and pushed. Spring Boot scaffold starts; no Aeron runtime recording was performed in Phase 0.
- Phase 1: PASS against the earlier requirements. Current fixed event list uses `OrderPlaced`, `TradeExecuted`, and `OrderCancelled`; 3 JUnit tests passed for deterministic replay, duplicate rejection, and sequence-gap rejection.
- Phase 2: PASS. `TradingReplayDemo` is now a REST controller at `POST /api/demo/roundtrip`; `ReplayService` coordinates Record → Replay → Verify; the Spring-managed `AeronArchiveGateway` starts one real embedded MediaDriver + Archive per app lifetime. Six IPC events were recorded and replayed with state match. Two simultaneous HTTP requests returned JSON with recording IDs `0` and `1`, six published/replayed events, and `stateMatched: true`; both Archive positions reached `544`. `mvn test` passed all 5 tests, including the real Archive round trip and concurrent-call serialization.
- JUnit is explicitly aligned to Jupiter 5.13.4 and Platform 1.13.4, avoiding Spring Boot's default JUnit 6 dependency management.
- The `startRecording` method returns a recording subscription ID, not the Archive recording ID. The demo queries `listRecordingsForUri` to obtain the recording ID before calling replay.
- Agrona 2.6.1 needs `--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED`; Maven Surefire and Spring Boot run have this configured.
- Each application startup writes to a unique folder under `target/aeron-phase2-runs`; requests within that app share one Archive but use separate streams. This validates same-process recording/replay and HTTP request isolation, not multi-JVM recovery or crash durability.
- The architecture refinement notes that a canonical state digest and a downstream event vocabulary including `OrderStatusChanged` have not yet been implemented. Preserve the Phase 1 results and surface this gap when planning subsequent work.

## Phase 3 result — PASS

- `scripts/run-phase3-demo.ps1` runs the full existing Maven suite, then coordinates separate Archive/MediaDriver, Publisher, and Consumer JVMs on local Aeron IPC.
- Verified run directory: `target/aeron-phase3-runs/run-20261014-003738-141`. The initial consumer processed sequences 1–2, then the harness forcibly stopped its JVM. The publisher and Archive continued recording sequences 3–6.
- The restarted consumer replayed sequences 1–4 from recording ID `0` through Archive position `352`, skipped overlapping live sequences 3–4, applied live sequences 5–6, and printed `STATE_RECOVERY=PASS`.
- Final expected state: last sequence `6`; one active BUY order `B-1001`, price `101`, remaining quantity `3`; trade count `2`; cumulative traded quantity `7`. The recording advanced through position `544` after all six events.
- All 5 Maven tests passed. The runner preserves per-process stdout/stderr logs and Archive files under the run directory.
- This is a single-machine consumer-restart experiment with real Aeron Archive, not host-level HA, guaranteed disk durability, or evidence of the exact OKX design.
- One learning simplification remains: Phase 3 verifies explicit expected snapshot fields rather than a canonical state hash. Do not describe it as hash comparison.

## Technical boundaries to keep visible

- Do not equate a business sequence number with an Aeron recording position.
- Do not claim Archive is a scheduler or that replay guarantees exactly-once side effects.
- Do not call local three-process testing host-level HA or proof of OKX production architecture.
- Verify Archive recording progress/durability and replay-to-live continuity; fail closed on gaps.

## Continuation

Next unfinished phase: **Phase 4 — Reliability Interview Drills**. Phase 3 is complete; stop and wait for the user to say `继续 Phase 4` before adding failure-injection experiments.
