package dev.playground.replaylab.service;

import dev.playground.replaylab.gateway.AeronArchiveGateway;
import dev.playground.replaylab.model.TradingEvent;
import dev.playground.replaylab.model.TradingState;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.List;
import java.util.Objects;

/** Coordinates a Phase 2 record, replay, and business-state verification. */
@Component
public final class ReplayService
{
    private final AeronArchiveGateway gateway;

    public ReplayService(final AeronArchiveGateway gateway)
    {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
    }

    public synchronized Result recordReplayAndVerify(final List<TradingEvent> events) throws IOException
    {
        Objects.requireNonNull(events, "events");
        if (events.isEmpty())
        {
            throw new IllegalArgumentException("At least one trading event is required");
        }

        final AeronArchiveGateway.Recording recording = gateway.record(events);
        final List<TradingEvent> replayedEvents = gateway.replay(recording, events.size());
        final TradingState publishedState = new TradingState();
        for (final TradingEvent event : events)
        {
            publishedState.apply(event);
        }

        final TradingState replayedState = new TradingState();
        for (final TradingEvent event : replayedEvents)
        {
            replayedState.apply(event);
        }

        final boolean stateMatched = events.equals(replayedEvents) &&
            publishedState.snapshot().equals(replayedState.snapshot());
        System.out.println("ROUND_TRIP_EVENTS=" + replayedEvents.size() + "/" + events.size());
        System.out.println("ROUND_TRIP_ORDER_MATCH=" + events.equals(replayedEvents));
        System.out.println("STATE_MATCHED=" + stateMatched);
        return new Result(
            recording.getRecordingId(),
            recording.getPublicationStopPosition(),
            recording.getArchiveRecordedPosition(),
            events.size(),
            replayedEvents,
            stateMatched,
            replayedState.snapshot());
    }

    public static final class Result
    {
        private final long recordingId;
        private final long publicationStopPosition;
        private final long archiveRecordedPosition;
        private final int publishedEvents;
        private final List<TradingEvent> replayedEvents;
        private final boolean stateMatched;
        private final TradingState.Snapshot reconstructedState;

        Result(
            final long recordingId,
            final long publicationStopPosition,
            final long archiveRecordedPosition,
            final int publishedEvents,
            final List<TradingEvent> replayedEvents,
            final boolean stateMatched,
            final TradingState.Snapshot reconstructedState)
        {
            this.recordingId = recordingId;
            this.publicationStopPosition = publicationStopPosition;
            this.archiveRecordedPosition = archiveRecordedPosition;
            this.publishedEvents = publishedEvents;
            this.replayedEvents = List.copyOf(replayedEvents);
            this.stateMatched = stateMatched;
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

        public int getPublishedEvents()
        {
            return publishedEvents;
        }

        public int getReplayedEventCount()
        {
            return replayedEvents.size();
        }

        public boolean isStateMatched()
        {
            return stateMatched;
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
