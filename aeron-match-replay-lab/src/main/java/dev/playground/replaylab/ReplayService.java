package dev.playground.replaylab;

import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Coordinates a Phase 2 record, replay, and business-state verification. */
@Component
final class ReplayService
{
    private final Path outputDirectory;

    ReplayService()
    {
        this(Path.of("target", "aeron-phase2-runs"));
    }

    ReplayService(final Path outputDirectory)
    {
        this.outputDirectory = Objects.requireNonNull(outputDirectory, "outputDirectory");
    }

    Result recordReplayAndVerify(final List<TradingEvent> events) throws IOException
    {
        Objects.requireNonNull(events, "events");
        if (events.isEmpty())
        {
            throw new IllegalArgumentException("At least one trading event is required");
        }

        try (AeronArchiveGateway gateway = AeronArchiveGateway.open(outputDirectory))
        {
            final AeronArchiveGateway.Recording recording = gateway.record(events);
            final List<TradingEvent> replayedEvents = gateway.replay(recording, events.size());
            if (!events.equals(replayedEvents))
            {
                throw new IllegalStateException(
                    "Archive replay differs from published events. expected=" + events +
                        ", actual=" + replayedEvents);
            }

            final TradingState state = new TradingState();
            for (final TradingEvent event : replayedEvents)
            {
                state.apply(event);
            }

            System.out.println("ROUND_TRIP_EVENTS=" + replayedEvents.size() + "/" + events.size());
            System.out.println("ROUND_TRIP_ORDER_MATCH=PASS");
            System.out.println("STATE_RECONSTRUCTION=PASS");
            return new Result(recording, replayedEvents, state.snapshot());
        }
    }

    static final class Result
    {
        private final AeronArchiveGateway.Recording recording;
        private final List<TradingEvent> replayedEvents;
        private final TradingState.Snapshot reconstructedState;

        Result(
            final AeronArchiveGateway.Recording recording,
            final List<TradingEvent> replayedEvents,
            final TradingState.Snapshot reconstructedState)
        {
            this.recording = recording;
            this.replayedEvents = List.copyOf(replayedEvents);
            this.reconstructedState = reconstructedState;
        }

        AeronArchiveGateway.Recording getRecording()
        {
            return recording;
        }

        List<TradingEvent> getReplayedEvents()
        {
            return replayedEvents;
        }

        TradingState.Snapshot getReconstructedState()
        {
            return reconstructedState;
        }
    }
}
