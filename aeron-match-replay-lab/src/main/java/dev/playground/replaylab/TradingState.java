package dev.playground.replaylab;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

public final class TradingState
{
    private final Map<String, ActiveOrder> activeOrders = new HashMap<>();
    private long lastProcessedSequenceNumber;
    private long executedTradeCount;
    private long cumulativeTradedQuantity;

    public void apply(final TradingEvent event)
    {
        Objects.requireNonNull(event, "event");
        validateSequence(event.sequenceNumber());

        if (event instanceof TradingEvent.OrderPlaced placed)
        {
            apply(placed);
        }
        else if (event instanceof TradingEvent.TradeExecuted trade)
        {
            apply(trade);
        }
        else if (event instanceof TradingEvent.OrderCancelled cancelled)
        {
            apply(cancelled);
        }
        else
        {
            throw new IllegalArgumentException("Unsupported event type: " + event.getClass().getName());
        }

        lastProcessedSequenceNumber = event.sequenceNumber();
    }

    public Snapshot snapshot()
    {
        return new Snapshot(
            lastProcessedSequenceNumber,
            Collections.unmodifiableMap(new TreeMap<>(activeOrders)),
            executedTradeCount,
            cumulativeTradedQuantity);
    }

    private void validateSequence(final long sequenceNumber)
    {
        if (sequenceNumber <= lastProcessedSequenceNumber)
        {
            throw new IllegalStateException(
                "Duplicate or old event: last=" + lastProcessedSequenceNumber + ", received=" + sequenceNumber);
        }

        if (lastProcessedSequenceNumber == Long.MAX_VALUE || sequenceNumber != lastProcessedSequenceNumber + 1)
        {
            throw new IllegalStateException(
                "Sequence gap: expected=" + (lastProcessedSequenceNumber + 1) + ", received=" + sequenceNumber);
        }
    }

    private void apply(final TradingEvent.OrderPlaced event)
    {
        validateText(event.orderId(), "orderId");
        validatePositive(event.price(), "price");
        validatePositive(event.quantity(), "quantity");
        if (activeOrders.containsKey(event.orderId()))
        {
            throw new IllegalStateException("Order already active: " + event.orderId());
        }

        activeOrders.put(
            event.orderId(), new ActiveOrder(event.orderId(), event.side(), event.price(), event.quantity()));
    }

    private void apply(final TradingEvent.TradeExecuted event)
    {
        validatePositive(event.price(), "trade price");
        validatePositive(event.quantity(), "trade quantity");
        if (event.buyOrderId().equals(event.sellOrderId()))
        {
            throw new IllegalStateException("A trade must reference two different orders");
        }

        final ActiveOrder buyOrder = requireActiveOrder(event.buyOrderId());
        final ActiveOrder sellOrder = requireActiveOrder(event.sellOrderId());
        if (buyOrder.side() != TradingEvent.Side.BUY || sellOrder.side() != TradingEvent.Side.SELL)
        {
            throw new IllegalStateException("Trade order sides do not match buy and sell roles");
        }
        if (event.quantity() > buyOrder.remainingQuantity() || event.quantity() > sellOrder.remainingQuantity())
        {
            throw new IllegalStateException("Trade quantity exceeds an order's remaining quantity");
        }

        final long nextTradeCount = Math.addExact(executedTradeCount, 1);
        final long nextTradedQuantity = Math.addExact(cumulativeTradedQuantity, event.quantity());
        updateRemainingQuantity(buyOrder, event.quantity());
        updateRemainingQuantity(sellOrder, event.quantity());
        executedTradeCount = nextTradeCount;
        cumulativeTradedQuantity = nextTradedQuantity;
    }

    private void apply(final TradingEvent.OrderCancelled event)
    {
        validateText(event.orderId(), "orderId");
        if (activeOrders.remove(event.orderId()) == null)
        {
            throw new IllegalStateException("Cannot cancel an inactive order: " + event.orderId());
        }
    }

    private ActiveOrder requireActiveOrder(final String orderId)
    {
        final ActiveOrder order = activeOrders.get(orderId);
        if (order == null)
        {
            throw new IllegalStateException("Order is not active: " + orderId);
        }
        return order;
    }

    private void updateRemainingQuantity(final ActiveOrder order, final long tradedQuantity)
    {
        final long remainingQuantity = order.remainingQuantity() - tradedQuantity;
        if (remainingQuantity == 0)
        {
            activeOrders.remove(order.orderId());
        }
        else
        {
            activeOrders.put(
                order.orderId(),
                new ActiveOrder(order.orderId(), order.side(), order.price(), remainingQuantity));
        }
    }

    private void validatePositive(final long value, final String fieldName)
    {
        if (value <= 0)
        {
            throw new IllegalArgumentException(fieldName + " must be positive");
        }
    }

    private void validateText(final String value, final String fieldName)
    {
        if (value.isBlank())
        {
            throw new IllegalArgumentException(fieldName + " must not be blank");
        }
    }

    public record ActiveOrder(String orderId, TradingEvent.Side side, long price, long remainingQuantity)
    {
    }

    public record Snapshot(
        long lastProcessedSequenceNumber,
        Map<String, ActiveOrder> activeOrders,
        long executedTradeCount,
        long cumulativeTradedQuantity)
    {
    }
}
