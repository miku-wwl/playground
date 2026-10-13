# Chat Handoff — Aeron Match Replay Lab

Updated: 2026-10-13

## Current checkout

- Workspace: `D:\workshop\oct\playground\aeron-match-replay-lab`
- Branch: `main`
- Phase 0 commit pushed to GitHub: `9e2e278318662c18fe17f5c92e3c7a4470cd5c22`
- Phase 1 implementation and handoff notes pushed to GitHub as `d3f4e93f4ef8c5b684892eb7deb4b43c3c1c9720`; local, tracking, and live remote SHAs matched after push.
- No repository `AGENTS.md`, README, prior planning file, or prior handoff file was present when this note was created.

## User-supplied architecture update

The learning story is now a latency-sensitive upstream publisher, Aeron transport and Archive recording, and an independently restartable downstream consumer that replays missed events and catches up with the live stream. Treat this as a simplified learning hypothesis; do not claim the user's OKX team had these exact processes or downstream workloads.

The most important Phase 3 change is from a single-process reset/replay demo to three independent Java processes: publisher, Archive plus its MediaDriver, and consumer. The publisher continues while the consumer is stopped; the restarted consumer recovers from a recording/checkpoint, replays missed events, transitions to live, and verifies its resulting projection.

## Preserved progress

- Phase 0: PASS and pushed. Spring Boot scaffold starts; no Aeron runtime recording was performed in Phase 0.
- Phase 1: PASS against the earlier requirements. Current fixed event list uses `OrderPlaced`, `TradeExecuted`, and `OrderCancelled`; 3 JUnit tests passed for deterministic replay, duplicate rejection, and sequence-gap rejection.
- Phase 2: PASS. `TradingReplayDemo` is the command-line entry point, `ReplayService` coordinates Record → Replay → Verify, and `AeronArchiveGateway` uses the actual Aeron 1.53.3 APIs with embedded MediaDriver + Archive. Six IPC events were recorded; the Archive position reached publication position `544`; catalog lookup returned recording ID `0`; a distinct replay stream delivered all six in sequence. The Archive directory contained `0-0.rec`, `archive.catalog`, and `archive-mark.dat`. `mvn test` passed all 4 tests, and `mvn -q spring-boot:run` ended with `ROUND_TRIP_ORDER_MATCH=PASS` and `STATE_RECONSTRUCTION=PASS`.
- JUnit is explicitly aligned to Jupiter 5.13.4 and Platform 1.13.4, avoiding Spring Boot's default JUnit 6 dependency management.
- The `startRecording` method returns a recording subscription ID, not the Archive recording ID. The demo queries `listRecordingsForUri` to obtain the recording ID before calling replay.
- Agrona 2.6.1 needs `--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED`; Maven Surefire and Spring Boot run have this configured.
- Phase 2 writes each demo run to a unique folder under `target/aeron-phase2-runs`. It validates same-process recording and replay, not multi-JVM recovery or crash durability.
- The architecture refinement notes that a canonical state digest and a downstream event vocabulary including `OrderStatusChanged` have not yet been implemented. Preserve the Phase 1 results and surface this gap when planning subsequent work.

## Technical boundaries to keep visible

- Do not equate a business sequence number with an Aeron recording position.
- Do not claim Archive is a scheduler or that replay guarantees exactly-once side effects.
- Do not call local three-process testing host-level HA or proof of OKX production architecture.
- Verify Archive recording progress/durability and replay-to-live continuity; fail closed on gaps.

## Continuation

Next unfinished phase: **Phase 3 — Distributed Consumer Recovery**. Wait for the user to say `继续 Phase 3`; keep the project one phase at a time.
