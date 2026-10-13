package dev.playground.replaylab;

import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.List;

@Component
public final class TradingReplayDemo implements CommandLineRunner
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

    @Override
    public void run(final String... args) throws IOException
    {
        System.out.println("=== Phase 2: real Aeron Archive record and replay ===");
        final ReplayService.Result result = replayService.recordReplayAndVerify(DEMO_EVENTS);
        System.out.println("RECORDING_ID=" + result.getRecording().getRecordingId());
        System.out.println("REPLAYED_TRADING_STATE=" + result.getReconstructedState());
    }

    static List<TradingEvent> demoEvents()
    {
        return DEMO_EVENTS;
    }
}
