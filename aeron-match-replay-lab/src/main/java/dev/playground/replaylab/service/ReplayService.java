package dev.playground.replaylab.service;

import dev.playground.replaylab.gateway.AeronArchiveGateway;
import dev.playground.replaylab.model.TradingEvent;
import dev.playground.replaylab.model.TradingState;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Coordinates a Phase 2 record, replay, and business-state verification. */
@Component
public final class ReplayService
{
    private final Path outputDirectory;

    public ReplayService()
    {
        this(Path.of("target", "aeron-phase2-runs"));
    }

    public ReplayService(final Path outputDirectory)
    {
        this.outputDirectory = Objects.requireNonNull(outputDirectory, "outputDirectory");
    }

    public Result recordReplayAndVerify(final List<TradingEvent> events) throws IOException
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
            return new Result(
                recording.getRecordingId(),
                recording.getPublicationStopPosition(),
                recording.getArchiveRecordedPosition(),
                replayedEvents,
                state.snapshot());
        }
    }

    public static final class Result
    {
        private final long recordingId;
        private final long publicationStopPosition;
        private final long archiveRecordedPosition;
        private final List<TradingEvent> replayedEvents;
        private final TradingState.Snapshot reconstructedState;

        Result(
            final long recordingId,
            final long publicationStopPosition,
            final long archiveRecordedPosition,
            final List<TradingEvent> replayedEvents,
            final TradingState.Snapshot reconstructedState)
        {
            this.recordingId = recordingId;
            this.publicationStopPosition = publicationStopPosition;
            this.archiveRecordedPosition = archiveRecordedPosition;
            this.replayedEvents = List.copyOf(replayedEvents);
            this.reconstructedState = reconstructedState;
        }

        public long getRecordingId()
        {
            return recordingId;
        }

        public long getPublicationStopPosition()
        {
            return publicationStopPosition;
        }

        public long getArchiveRecordedPosition()
        {
            return archiveRecordedPosition;
        }

        public List<TradingEvent> getReplayedEvents()
        {
            return replayedEvents;
        }

        public TradingState.Snapshot getReconstructedState()
        {
            return reconstructedState;
        }
    }
}
