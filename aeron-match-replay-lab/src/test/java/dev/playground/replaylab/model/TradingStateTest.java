package dev.playground.replaylab.model;

import dev.playground.replaylab.controller.TradingReplayDemo;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TradingStateTest
{
    @Test
    void replayingTheSameOrderedEventsProducesTheSameState()
    {
        final TradingState.Snapshot firstReplay = replayAllDemoEvents();
        final TradingState.Snapshot secondReplay = replayAllDemoEvents();

        assertEquals(firstReplay, secondReplay);
        assertEquals(6, firstReplay.getLastProcessedSequenceNumber());
        assertEquals(2, firstReplay.getExecutedTradeCount());
        assertEquals(7, firstReplay.getCumulativeTradedQuantity());
        assertEquals(3, firstReplay.getActiveOrders().get("B-1001").getRemainingQuantity());
    }

    @Test
    void duplicateSequenceIsRejectedWithoutChangingState()
    {
        final TradingState state = new TradingState();
        final TradingEvent firstEvent = TradingReplayDemo.demoEvents().get(0);
        state.apply(firstEvent);
        final TradingState.Snapshot beforeDuplicate = state.snapshot();

        assertThrows(IllegalStateException.class, () -> state.apply(firstEvent));
        assertEquals(beforeDuplicate, state.snapshot());
    }

    @Test
    void sequenceGapIsRejectedWithoutAdvancingState()
    {
        final TradingState state = new TradingState();
        final List<TradingEvent> events = TradingReplayDemo.demoEvents();
        state.apply(events.get(0));
        final TradingState.Snapshot beforeGap = state.snapshot();

        assertThrows(IllegalStateException.class, () -> state.apply(events.get(2)));
        assertEquals(beforeGap, state.snapshot());
    }

    private TradingState.Snapshot replayAllDemoEvents()
    {
        final TradingState state = new TradingState();
        for (final TradingEvent event : TradingReplayDemo.demoEvents())
        {
            state.apply(event);
        }
        return state.snapshot();
    }
}
