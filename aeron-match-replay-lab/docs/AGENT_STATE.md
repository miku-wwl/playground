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
- The scaffold was committed and pushed to `main` as `9e2e278318662c18fe17f5c92e3c7a4470cd5c22`. Local `HEAD`, `origin/main`, and live GitHub `main` were checked equal after the push.
- Phase 0 did not start MediaDriver or Archive and did not record/replay events.

### Phase 1 — Deterministic downstream state: PASS against the prior acceptance; updated-model refinements remain

- `TradingEvent` currently defines `OrderPlaced`, `TradeExecuted`, and `OrderCancelled`.
- `TradingState` maintains active orders, remaining quantities, trade count, cumulative quantity, and last applied business sequence number.
- The six-event demo is an in-memory fixed list. It does not use Aeron and does not implement matching logic.
- Sequence numbers must be contiguous. Duplicate/old events and gaps are rejected without advancing the state. Snapshots sort active orders for repeatable comparison and display.
- Latest observed verification: `mvn -B clean test` passed 3 tests; `mvn -B package` passed; the executable Spring Boot JAR ran the six-event demo and ended at sequence 6 with one active order of quantity 3, 2 trade events, and cumulative quantity 7.
- Phase 1 files are currently local and uncommitted. Preserve them and their test evidence.
- Architecture-update alignment still to consider: the event examples now emphasize already-completed downstream results (`TradeExecuted`, `OrderCancelled`, `OrderStatusChanged`), while the current demo also includes `OrderPlaced`; the current code compares snapshots but does not emit an explicit canonical state digest. These are refinement targets, not evidence that the earlier tests failed.

### Remaining phases

- **Phase 2 — Real Aeron Record/Replay: NOT STARTED.** Use real Aeron and Archive APIs; publish, record, identify recordings, replay on a distinct subscription, and verify ordering/completeness. Prefer the current implementation and keep Aeron versions aligned.
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

The next unfinished implementation phase is Phase 2. Wait for the user's explicit instruction `继续 Phase 2` before starting it. Keep this project one phase at a time and report actual logs/tests at each phase boundary.
