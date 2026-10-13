# Agent State — Aeron Match Replay Lab

Updated: 2026-10-13

## Purpose and trust boundary

This is an independent local learning experiment for explaining Aeron transport, Aeron Archive recording/replay, and downstream recovery. It is not a reconstruction of OKX's proprietary implementation, matching algorithm, deployment topology, or downstream workloads.

The user's historical resume statement is the only stated evidence about the OKX experience: they contributed to a replay service using Aeron Archive to record and replay event streams for trading-state reconstruction and recovery after failures. The Machine A / Archive / Machine B design below is a learning hypothesis, not a verified description of OKX production architecture.

## Updated logical architecture

```text
Machine A — Match Engine Publisher
  emits ordered, already-completed result events
  does not run a real matching algorithm
          |
          | Aeron Publication
          v
     Aeron MediaDriver ------------------------------+
          |                                          |
          | Archive records stream                  | live stream
          v                                          v
     Aeron Archive                         Machine B — Consumer
     recording files                        derived projection
          |                                          |
          +---- replay from checkpoint/position -----+
                                                     |
                                      replay -> catch up -> live
```

Machine A is the latency-sensitive publisher. Machine B does asynchronous downstream work and maintains its own derived state. A consumer restart should not require the publisher or matching algorithm to restart. The Archive records identifiable streams and supports replay; it is not a task scheduler or a business-level exactly-once engine.

The target Phase 3 experiment uses three independently managed Java processes on one local machine: publisher, Archive with its required MediaDriver, and consumer. This validates process boundaries and consumer recovery, but does not prove host-level high availability or network fault tolerance.

The desired producer isolation is a goal to validate, not an assumption: channel, flow-control, Archive lag, and publisher back-pressure behavior remain to be designed and measured. Archive durability depends on its configured storage and sync policy. A same-host disk failure can still lose local recordings unless recordings are replicated or backed up.

## Phase status and verified evidence

### Phase 0 — Environment and Aeron architecture: PASS

- Existing project: `aeron-match-replay-lab`, Spring Boot 4.1.1, Java release 17, Aeron client/archive 1.53.3.
- Observed local toolchain: OpenJDK 21.0.6 and Maven 3.9.9.
- Uses the non-web Spring Boot starter; no HTTP server is configured.
- The scaffold was committed and pushed to `main` as `9e2e278318662c18fe17f5c92e3c7a4470cd5c22`. The Phase 1 implementation and handoff notes were pushed as `d3f4e93f4ef8c5b684892eb7deb4b43c3c1c9720`; local `HEAD`, `origin/main`, and live GitHub `main` were checked equal after the push.
- Phase 0 did not start MediaDriver or Archive and did not record/replay events.

### Phase 1 — Deterministic downstream state: PASS against the prior acceptance; updated-model refinements remain

- `TradingEvent` currently defines `OrderPlaced`, `TradeExecuted`, and `OrderCancelled`.
- `TradingState` maintains active orders, remaining quantities, trade count, cumulative quantity, and last applied business sequence number.
- The six-event demo is an in-memory fixed list. It does not use Aeron and does not implement matching logic.
- Sequence numbers must be contiguous. Duplicate/old events and gaps are rejected without advancing the state. Snapshots sort active orders for repeatable comparison and display.
- Latest observed Phase 1 verification before Archive integration: `mvn -B clean test` passed 3 tests; `mvn -B package` passed; the six-event state projection ended at sequence 6 with one active order of quantity 3, 2 trade events, and cumulative quantity 7.
- Architecture-update alignment still to consider: the event examples now emphasize already-completed downstream results (`TradeExecuted`, `OrderCancelled`, `OrderStatusChanged`), while the current demo also includes `OrderPlaced`; the current code compares snapshots but does not emit an explicit canonical state digest. These are refinement targets, not evidence that the earlier tests failed.

### Phase 2 — Real Aeron Archive record/replay: PASS

- `TradingReplayDemo` is the `CommandLineRunner` entry point, `ReplayService` coordinates record/replay/verification, and `AeronArchiveGateway` owns the real embedded `ArchivingMediaDriver`, Archive, Aeron client, and their resources. Trading events use Aeron IPC; replay uses a separate stream ID and session-bound subscription.
- `TradingEventCodec` serializes the three Phase 1 event types. Six events were published in sequence 1–6. The publication stop position and Archive recording position both reached `544` before recording was stopped.
- The Archive catalog was queried with `listRecordingsForUri`; the demo recording ID was `0`. Important API distinction: `startRecording` returned a subscription ID (`30` in this run), not the recording ID.
- Current runtime evidence: `mvn -q spring-boot:run` completed with `ROUND_TRIP_EVENTS=6/6`, `ROUND_TRIP_ORDER_MATCH=PASS`, and `STATE_RECONSTRUCTION=PASS`. The replayed state ended at sequence 6 with B-1001 quantity 3, 2 trades, and cumulative quantity 7.
- The run created real files in `target/aeron-phase2-runs/run-15262213981059113960/archive`: `0-0.rec`, `archive.catalog`, and `archive-mark.dat`. The recording position matched the publication stop position at `544`.
- Actual test evidence: `mvn -B '-Dmaven.compiler.showDeprecation=true' clean package` passed all 4 tests and built the executable JAR. JUnit dependency tree was checked and pinned to Jupiter 5.13.4 with JUnit Platform 1.13.4.
- Agrona 2.6.1 requires opening `java.base/jdk.internal.misc` for `org.agrona.UnsafeApi`; Maven Surefire and Spring Boot run are configured with `--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED`. This does not make a JAR invocation without the option work; use `mvn spring-boot:run` or pass the option to `java`.
- Each demo invocation writes to a fresh directory under `target/aeron-phase2-runs`. This proves real local recording/replay, but Phase 2 does not yet prove recovery across JVMs, stable archive reuse, crash durability, or production behavior. `mvn clean` removes these demo files.

### Remaining phases

- **Phase 2 — Real Aeron Record/Replay: PASS.** The local embedded Archive integration and ordered six-event replay passed. Cross-process persistence is not part of this phase.
- **Phase 3 — Distributed Consumer Recovery: NOT STARTED.** Replace the earlier single-process recovery idea with three independently managed local Java processes. The consumer must survive its own restart while the publisher continues, recover from a known recording/checkpoint, replay the gap, transition to live without loss or double application, and compare against independently calculated expected state.
- **Phase 4 — Failure injection and interview drills: NOT STARTED.** Cover consumer crash, duplicate replay, gaps, replay/live overlap, Archive lag, and producer/Archive failure boundaries.
- **Phase 5 — Interview cheat sheet: NOT STARTED.** Explain the distributed downstream-recovery story and its limitations without presenting the local simulation as historical OKX implementation evidence.

## Important correctness boundaries

- Business sequence number identifies logical business order and supports duplicate/gap detection. Aeron recording position identifies a byte position in an Archive recording. They are different checkpoints and must not be substituted for one another.
- A consumer checkpoint and an external side effect are not automatically atomic. Replay alone does not guarantee exactly-once business effects. Explain the chosen at-least-once behavior and any idempotency/deduplication mechanism.
- Replay can rebuild a projection or reprocess downstream events; it does not necessarily rerun the original matching algorithm.
- A replay-to-live transition must track both business sequence continuity and Archive/transport positions. Fail closed when continuity cannot be established.
- An in-process state reset is not proof of process-crash recovery. Phase 3 must use separate JVM invocations and preserve Archive recordings across consumer restarts.

## Next step

The next unfinished implementation phase is Phase 3. Wait for the user's explicit instruction `继续 Phase 3` before starting it. Keep this project one phase at a time and report actual logs/tests at each phase boundary.
