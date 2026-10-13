package dev.playground.replaylab.controller;

import dev.playground.replaylab.model.TradingEvent;
import dev.playground.replaylab.service.ReplayService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.util.List;

@RestController
@RequestMapping("/api/demo")
public final class TradingReplayDemo
{
    private final ReplayService replayService;

    private static final List<TradingEvent> DEMO_EVENTS = List.of(
        new TradingEvent.OrderPlaced(1, "B-1001", TradingEvent.Side.BUY, 101, 10),
        new TradingEvent.OrderPlaced(2, "S-2001", TradingEvent.Side.SELL, 100, 6),
        new TradingEvent.TradeExecuted(3, "B-1001", "S-2001", 100, 4),
        new TradingEvent.OrderCancelled(4, "S-2001"),
        new TradingEvent.OrderPlaced(5, "S-2002", TradingEvent.Side.SELL, 101, 3),
        new TradingEvent.TradeExecuted(6, "B-1001", "S-2002", 101, 3));

    public TradingReplayDemo(final ReplayService replayService)
    {
        this.replayService = replayService;
    }

    @PostMapping("/roundtrip")
    public RoundTripResponse roundTrip() throws IOException
    {
        final ReplayService.Result result = replayService.recordReplayAndVerify(DEMO_EVENTS);
        return new RoundTripResponse(
            result.getRecordingId(),
            result.getPublishedEvents(),
            result.getReplayedEventCount(),
            result.isStateMatched());
    }

    public static List<TradingEvent> demoEvents()
    {
        return DEMO_EVENTS;
    }

    public static final class RoundTripResponse
    {
        private final long recordingId;
        private final int publishedEvents;
        private final int replayedEvents;
        private final boolean stateMatched;

        RoundTripResponse(
            final long recordingId,
            final int publishedEvents,
            final int replayedEvents,
            final boolean stateMatched)
        {
            this.recordingId = recordingId;
            this.publishedEvents = publishedEvents;
            this.replayedEvents = replayedEvents;
            this.stateMatched = stateMatched;
        }

        public long getRecordingId()
        {
            return recordingId;
        }

        public int getPublishedEvents()
        {
            return publishedEvents;
        }

        public int getReplayedEvents()
        {
            return replayedEvents;
        }

        public boolean isStateMatched()
        {
            return stateMatched;
        }
    }
}
