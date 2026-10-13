package dev.playground.replaylab;

import java.util.Objects;

public sealed interface TradingEvent
    permits TradingEvent.OrderPlaced, TradingEvent.TradeExecuted, TradingEvent.OrderCancelled
{
    long sequenceNumber();

    enum Side
    {
        BUY,
        SELL
    }

    record OrderPlaced(long sequenceNumber, String orderId, Side side, long price, long quantity)
        implements TradingEvent
    {
        public OrderPlaced
        {
            Objects.requireNonNull(orderId, "orderId");
            Objects.requireNonNull(side, "side");
        }
    }

    record TradeExecuted(
        long sequenceNumber,
        String buyOrderId,
        String sellOrderId,
        long price,
        long quantity) implements TradingEvent
    {
        public TradeExecuted
        {
            Objects.requireNonNull(buyOrderId, "buyOrderId");
            Objects.requireNonNull(sellOrderId, "sellOrderId");
        }
    }

    record OrderCancelled(long sequenceNumber, String orderId) implements TradingEvent
    {
        public OrderCancelled
        {
            Objects.requireNonNull(orderId, "orderId");
        }
    }
}
