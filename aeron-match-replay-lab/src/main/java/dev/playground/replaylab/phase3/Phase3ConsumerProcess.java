package dev.playground.replaylab.phase3;

import dev.playground.replaylab.model.TradingEvent;
import dev.playground.replaylab.model.TradingState;
import io.aeron.Aeron;
import io.aeron.ChannelUri;
import io.aeron.Subscription;
import io.aeron.archive.client.AeronArchive;

import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

/** A fresh JVM either consumes the first live batch or recovers and catches up. */
public final class Phase3ConsumerProcess
{
    private static final int MAX_FRAGMENTS_PER_POLL = 16;

    private Phase3ConsumerProcess()
    {
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length != 2)
        {
            throw new IllegalArgumentException("Expected: <run-directory> <initial|recover>");
        }
        final Path runDirectory = Path.of(args[0]).toAbsolutePath();
        if ("initial".equals(args[1]))
        {
            consumeInitialBatch(runDirectory);
        }
        else if ("recover".equals(args[1]))
        {
            recoverAndCatchUp(runDirectory);
        }
        else
        {
            throw new IllegalArgumentException("Unknown consumer mode: " + args[1]);
        }
    }

    private static void consumeInitialBatch(final Path runDirectory) throws Exception
    {
        try (Aeron aeron = Phase3ProcessSupport.connectAeron(runDirectory);
             Subscription liveSubscription = aeron.addSubscription(
                 Phase3ProcessSupport.LIVE_CHANNEL,
                 Phase3ProcessSupport.LIVE_STREAM_ID))
        {
            System.out.println("INITIAL_CONSUMER_PID=" + ProcessHandle.current().pid());
            Phase3ProcessSupport.writeMarker(runDirectory, "consumer.initial.ready");
            Phase3ProcessSupport.await(liveSubscription::isConnected, "initial consumer live subscription");

            final TradingState state = new TradingState();
            final List<TradingEvent> received = receiveUntil(
                liveSubscription,
                Phase3ProcessSupport.REPLAY_PREFIX_EVENT_COUNT / 2,
                Duration.ofSeconds(30));
            for (final TradingEvent event : received)
            {
                state.apply(event);
                System.out.println("INITIAL_LIVE sequenceNumber=" + event.getSequenceNumber());
            }
            System.out.println("INITIAL_CONSUMER_STATE=" + state.snapshot());
            Phase3ProcessSupport.writeMarker(runDirectory, "consumer.initial.done");
            System.out.println("INITIAL_CONSUMER_WAITING_FOR_CRASH_SIMULATION");
            Phase3ProcessSupport.awaitMarker(runDirectory, "consumer.initial.stop", Duration.ofMinutes(2));
        }
        System.out.println("INITIAL_CONSUMER_STOPPED");
    }

    private static void recoverAndCatchUp(final Path runDirectory) throws Exception
    {
        try (Aeron aeron = Phase3ProcessSupport.connectAeron(runDirectory);
             AeronArchive archive = Phase3ProcessSupport.connectArchive(aeron);
             Subscription liveSubscription = aeron.addSubscription(
                 Phase3ProcessSupport.LIVE_CHANNEL,
                 Phase3ProcessSupport.LIVE_STREAM_ID))
        {
            final Properties manifest = Phase3ProcessSupport.readManifest(runDirectory);
            final long recordingId = Phase3ProcessSupport.getLong(manifest, "recordingId");
            final long recordingStart = Phase3ProcessSupport.getLong(manifest, "recordingStartPosition");
            final long replayBoundary = Phase3ProcessSupport.getLong(manifest, "replayBoundaryPosition");
            final int replayPrefixEvents = Math.toIntExact(
                Phase3ProcessSupport.getLong(manifest, "replayPrefixEvents"));

            Phase3ProcessSupport.await(liveSubscription::isConnected, "recovery consumer live subscription");
            final long maxRecordedPosition = archive.getMaxRecordedPosition(recordingId);
            if (maxRecordedPosition < replayBoundary)
            {
                throw new IllegalStateException("Archive is behind the requested replay boundary: max=" +
                    maxRecordedPosition + ", boundary=" + replayBoundary);
            }
            System.out.println("RECOVERY_CONSUMER_PID=" + ProcessHandle.current().pid());
            System.out.println("RECORDING_ID=" + recordingId +
                " startPosition=" + recordingStart +
                " replayBoundaryPosition=" + replayBoundary +
                " archiveMaxPosition=" + maxRecordedPosition);
            Phase3ProcessSupport.writeMarker(runDirectory, "consumer.recovery.ready");

            final long replaySessionId = archive.startReplay(
                recordingId,
                recordingStart,
                replayBoundary - recordingStart,
                Phase3ProcessSupport.REPLAY_CHANNEL,
                Phase3ProcessSupport.REPLAY_STREAM_ID);
            final String replayChannel = ChannelUri.addSessionId(
                Phase3ProcessSupport.REPLAY_CHANNEL,
                (int)replaySessionId);

            final TradingState recoveredState = new TradingState();
            final List<TradingEvent> liveBuffer = new ArrayList<>();
            try (Subscription replaySubscription = aeron.addSubscription(
                replayChannel,
                Phase3ProcessSupport.REPLAY_STREAM_ID))
            {
                Phase3ProcessSupport.await(replaySubscription::isConnected, "Archive replay subscription");
                final long deadline = System.nanoTime() + Phase3ProcessSupport.OPERATION_TIMEOUT.toNanos();
                while (recoveredState.snapshot().getLastProcessedSequenceNumber() < replayPrefixEvents)
                {
                    if (System.nanoTime() >= deadline)
                    {
                        throw new IllegalStateException("Timed out replaying the recorded prefix");
                    }

                    pollIntoState(replaySubscription, recoveredState, "RECOVERY_REPLAY");
                    pollIntoList(liveSubscription, liveBuffer);
                }
            }
            finally
            {
                archive.stopReplay(replaySessionId);
            }

            System.out.println("REPLAY_PREFIX_COMPLETE lastSequence=" +
                recoveredState.snapshot().getLastProcessedSequenceNumber());
            applyNewEvents(recoveredState, liveBuffer, "LIVE_CATCH_UP");

            final long liveDeadline = System.nanoTime() + Phase3ProcessSupport.OPERATION_TIMEOUT.toNanos();
            while (recoveredState.snapshot().getLastProcessedSequenceNumber() <
                Phase3ProcessSupport.TOTAL_EVENT_COUNT)
            {
                if (System.nanoTime() >= liveDeadline)
                {
                    throw new IllegalStateException("Timed out waiting for live events after Archive replay");
                }
                liveBuffer.clear();
                pollIntoList(liveSubscription, liveBuffer);
                applyNewEvents(recoveredState, liveBuffer, "LIVE_CATCH_UP");
            }

            Phase3ProcessSupport.awaitMarker(runDirectory, "publisher.done", Duration.ofSeconds(20));
            verifyExpectedState(recoveredState);
            System.out.println("RECOVERED_STATE=" + recoveredState.snapshot());
            System.out.println("STATE_RECOVERY=PASS");
            Phase3ProcessSupport.writeMarker(runDirectory, "consumer.recovery.done");
        }
    }

    private static List<TradingEvent> receiveUntil(
        final Subscription subscription,
        final int expectedCount,
        final Duration timeout)
    {
        final List<TradingEvent> events = new ArrayList<>(expectedCount);
        final long deadline = System.nanoTime() + timeout.toNanos();
        while (events.size() < expectedCount)
        {
            if (System.nanoTime() >= deadline)
            {
                throw new IllegalStateException("Timed out waiting for initial live events");
            }
            pollIntoList(subscription, events, expectedCount - events.size());
        }
        return events;
    }

    private static void pollIntoState(
        final Subscription subscription,
        final TradingState state,
        final String logPrefix)
    {
        subscription.poll((buffer, offset, length, header) ->
        {
            final TradingEvent event = Phase3ProcessSupport.decode(buffer, offset, length);
            state.apply(event);
            System.out.println(logPrefix + " sequenceNumber=" + event.getSequenceNumber());
        }, MAX_FRAGMENTS_PER_POLL);
    }

    private static void pollIntoList(final Subscription subscription, final List<TradingEvent> events)
    {
        pollIntoList(subscription, events, MAX_FRAGMENTS_PER_POLL);
    }

    private static void pollIntoList(
        final Subscription subscription,
        final List<TradingEvent> events,
        final int fragmentLimit)
    {
        subscription.poll((buffer, offset, length, header) ->
            events.add(Phase3ProcessSupport.decode(buffer, offset, length)), fragmentLimit);
    }

    private static void applyNewEvents(
        final TradingState state,
        final List<TradingEvent> events,
        final String logPrefix)
    {
        for (final TradingEvent event : events)
        {
            final long lastSequence = state.snapshot().getLastProcessedSequenceNumber();
            if (event.getSequenceNumber() <= lastSequence)
            {
                System.out.println("DUPLICATE_LIVE_IGNORED sequenceNumber=" + event.getSequenceNumber());
                continue;
            }
            state.apply(event);
            System.out.println(logPrefix + " sequenceNumber=" + event.getSequenceNumber());
        }
    }

    private static void verifyExpectedState(final TradingState state)
    {
        final TradingState.Snapshot snapshot = state.snapshot();
        final TradingState.ActiveOrder remainingBuyOrder = snapshot.getActiveOrders().get("B-1001");
        final boolean matches = snapshot.getLastProcessedSequenceNumber() == 6 &&
            snapshot.getActiveOrders().size() == 1 &&
            remainingBuyOrder != null &&
            remainingBuyOrder.getSide() == TradingEvent.Side.BUY &&
            remainingBuyOrder.getPrice() == 101 &&
            remainingBuyOrder.getRemainingQuantity() == 3 &&
            snapshot.getExecutedTradeCount() == 2 &&
            snapshot.getCumulativeTradedQuantity() == 7;
        if (!matches)
        {
            throw new IllegalStateException("Recovered state differs from the expected demo state: " + snapshot);
        }
    }
}
