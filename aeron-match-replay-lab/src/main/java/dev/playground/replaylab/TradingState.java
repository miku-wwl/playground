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
        validateSequence(event.getSequenceNumber());

        if (event instanceof TradingEvent.OrderPlaced)
        {
            apply((TradingEvent.OrderPlaced)event);
        }
        else if (event instanceof TradingEvent.TradeExecuted)
        {
            apply((TradingEvent.TradeExecuted)event);
        }
        else if (event instanceof TradingEvent.OrderCancelled)
        {
            apply((TradingEvent.OrderCancelled)event);
        }
        else
        {
            throw new IllegalArgumentException("Unsupported event type: " + event.getClass().getName());
        }

        lastProcessedSequenceNumber = event.getSequenceNumber();
    }

    public Snapshot snapshot()
    {
        return new Snapshot(
            lastProcessedSequenceNumber,
            activeOrders,
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
        validateText(event.getOrderId(), "orderId");
        validatePositive(event.getPrice(), "price");
        validatePositive(event.getQuantity(), "quantity");
        if (activeOrders.containsKey(event.getOrderId()))
        {
            throw new IllegalStateException("Order already active: " + event.getOrderId());
        }

        activeOrders.put(
            event.getOrderId(),
            new ActiveOrder(event.getOrderId(), event.getSide(), event.getPrice(), event.getQuantity()));
    }

    private void apply(final TradingEvent.TradeExecuted event)
    {
        validatePositive(event.getPrice(), "trade price");
        validatePositive(event.getQuantity(), "trade quantity");
        if (event.getBuyOrderId().equals(event.getSellOrderId()))
        {
            throw new IllegalStateException("A trade must reference two different orders");
        }

        final ActiveOrder buyOrder = requireActiveOrder(event.getBuyOrderId());
        final ActiveOrder sellOrder = requireActiveOrder(event.getSellOrderId());
        if (buyOrder.getSide() != TradingEvent.Side.BUY || sellOrder.getSide() != TradingEvent.Side.SELL)
        {
            throw new IllegalStateException("Trade order sides do not match buy and sell roles");
        }
        if (event.getQuantity() > buyOrder.getRemainingQuantity() ||
            event.getQuantity() > sellOrder.getRemainingQuantity())
        {
            throw new IllegalStateException("Trade quantity exceeds an order's remaining quantity");
        }

        final long nextTradeCount = Math.addExact(executedTradeCount, 1);
        final long nextTradedQuantity = Math.addExact(cumulativeTradedQuantity, event.getQuantity());
        updateRemainingQuantity(buyOrder, event.getQuantity());
        updateRemainingQuantity(sellOrder, event.getQuantity());
        executedTradeCount = nextTradeCount;
        cumulativeTradedQuantity = nextTradedQuantity;
    }

    private void apply(final TradingEvent.OrderCancelled event)
    {
        validateText(event.getOrderId(), "orderId");
        if (activeOrders.remove(event.getOrderId()) == null)
        {
            throw new IllegalStateException("Cannot cancel an inactive order: " + event.getOrderId());
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
        final long remainingQuantity = order.getRemainingQuantity() - tradedQuantity;
        if (remainingQuantity == 0)
        {
            activeOrders.remove(order.getOrderId());
        }
        else
        {
            activeOrders.put(
                order.getOrderId(),
                new ActiveOrder(order.getOrderId(), order.getSide(), order.getPrice(), remainingQuantity));
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

    public static final class ActiveOrder
    {
        private final String orderId;
        private final TradingEvent.Side side;
        private final long price;
        private final long remainingQuantity;

        public ActiveOrder(
            final String orderId,
            final TradingEvent.Side side,
            final long price,
            final long remainingQuantity)
        {
            this.orderId = Objects.requireNonNull(orderId, "orderId");
            this.side = Objects.requireNonNull(side, "side");
            this.price = price;
            this.remainingQuantity = remainingQuantity;
        }

        public String getOrderId()
        {
            return orderId;
        }

        public TradingEvent.Side getSide()
        {
            return side;
        }

        public long getPrice()
        {
            return price;
        }

        public long getRemainingQuantity()
        {
            return remainingQuantity;
        }

        @Override
        public boolean equals(final Object other)
        {
            if (this == other)
            {
                return true;
            }
            if (!(other instanceof ActiveOrder))
            {
                return false;
            }
            final ActiveOrder that = (ActiveOrder)other;
            return price == that.price &&
                remainingQuantity == that.remainingQuantity &&
                orderId.equals(that.orderId) &&
                side == that.side;
        }

        @Override
        public int hashCode()
        {
            return Objects.hash(orderId, side, price, remainingQuantity);
        }

        @Override
        public String toString()
        {
            return "ActiveOrder[orderId=" + orderId +
                ", side=" + side +
                ", price=" + price +
                ", remainingQuantity=" + remainingQuantity + "]";
        }
    }

    public static final class Snapshot
    {
        private final long lastProcessedSequenceNumber;
        private final Map<String, ActiveOrder> activeOrders;
        private final long executedTradeCount;
        private final long cumulativeTradedQuantity;

        public Snapshot(
            final long lastProcessedSequenceNumber,
            final Map<String, ActiveOrder> activeOrders,
            final long executedTradeCount,
            final long cumulativeTradedQuantity)
        {
            this.lastProcessedSequenceNumber = lastProcessedSequenceNumber;
            this.activeOrders = Collections.unmodifiableMap(new TreeMap<>(activeOrders));
            this.executedTradeCount = executedTradeCount;
            this.cumulativeTradedQuantity = cumulativeTradedQuantity;
        }

        public long getLastProcessedSequenceNumber()
        {
            return lastProcessedSequenceNumber;
        }

        public Map<String, ActiveOrder> getActiveOrders()
        {
            return activeOrders;
        }

        public long getExecutedTradeCount()
        {
            return executedTradeCount;
        }

        public long getCumulativeTradedQuantity()
        {
            return cumulativeTradedQuantity;
        }

        @Override
        public boolean equals(final Object other)
        {
            if (this == other)
            {
                return true;
            }
            if (!(other instanceof Snapshot))
            {
                return false;
            }
            final Snapshot that = (Snapshot)other;
            return lastProcessedSequenceNumber == that.lastProcessedSequenceNumber &&
                executedTradeCount == that.executedTradeCount &&
                cumulativeTradedQuantity == that.cumulativeTradedQuantity &&
                activeOrders.equals(that.activeOrders);
        }

        @Override
        public int hashCode()
        {
            return Objects.hash(
                lastProcessedSequenceNumber, activeOrders, executedTradeCount, cumulativeTradedQuantity);
        }

        @Override
        public String toString()
        {
            return "Snapshot[lastProcessedSequenceNumber=" + lastProcessedSequenceNumber +
                ", activeOrders=" + activeOrders +
                ", executedTradeCount=" + executedTradeCount +
                ", cumulativeTradedQuantity=" + cumulativeTradedQuantity + "]";
        }
    }
}
