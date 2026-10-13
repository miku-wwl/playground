package dev.playground.replaylab.model;

import java.util.Objects;

public interface TradingEvent
{
    long getSequenceNumber();

    enum Side
    {
        BUY,
        SELL
    }

    final class OrderPlaced implements TradingEvent
    {
        private final long sequenceNumber;
        private final String orderId;
        private final Side side;
        private final long price;
        private final long quantity;

        public OrderPlaced(
            final long sequenceNumber,
            final String orderId,
            final Side side,
            final long price,
            final long quantity)
        {
            this.sequenceNumber = sequenceNumber;
            this.orderId = Objects.requireNonNull(orderId, "orderId");
            this.side = Objects.requireNonNull(side, "side");
            this.price = price;
            this.quantity = quantity;
        }

        @Override
        public long getSequenceNumber()
        {
            return sequenceNumber;
        }

        public String getOrderId()
        {
            return orderId;
        }

        public Side getSide()
        {
            return side;
        }

        public long getPrice()
        {
            return price;
        }

        public long getQuantity()
        {
            return quantity;
        }

        @Override
        public boolean equals(final Object other)
        {
            if (this == other)
            {
                return true;
            }
            if (!(other instanceof OrderPlaced))
            {
                return false;
            }
            final OrderPlaced that = (OrderPlaced)other;
            return sequenceNumber == that.sequenceNumber &&
                price == that.price &&
                quantity == that.quantity &&
                orderId.equals(that.orderId) &&
                side == that.side;
        }

        @Override
        public int hashCode()
        {
            return Objects.hash(sequenceNumber, orderId, side, price, quantity);
        }

        @Override
        public String toString()
        {
            return "OrderPlaced[sequenceNumber=" + sequenceNumber +
                ", orderId=" + orderId +
                ", side=" + side +
                ", price=" + price +
                ", quantity=" + quantity + "]";
        }
    }

    final class TradeExecuted implements TradingEvent
    {
        private final long sequenceNumber;
        private final String buyOrderId;
        private final String sellOrderId;
        private final long price;
        private final long quantity;

        public TradeExecuted(
            final long sequenceNumber,
            final String buyOrderId,
            final String sellOrderId,
            final long price,
            final long quantity)
        {
            this.sequenceNumber = sequenceNumber;
            this.buyOrderId = Objects.requireNonNull(buyOrderId, "buyOrderId");
            this.sellOrderId = Objects.requireNonNull(sellOrderId, "sellOrderId");
            this.price = price;
            this.quantity = quantity;
        }

        @Override
        public long getSequenceNumber()
        {
            return sequenceNumber;
        }

        public String getBuyOrderId()
        {
            return buyOrderId;
        }

        public String getSellOrderId()
        {
            return sellOrderId;
        }

        public long getPrice()
        {
            return price;
        }

        public long getQuantity()
        {
            return quantity;
        }

        @Override
        public boolean equals(final Object other)
        {
            if (this == other)
            {
                return true;
            }
            if (!(other instanceof TradeExecuted))
            {
                return false;
            }
            final TradeExecuted that = (TradeExecuted)other;
            return sequenceNumber == that.sequenceNumber &&
                price == that.price &&
                quantity == that.quantity &&
                buyOrderId.equals(that.buyOrderId) &&
                sellOrderId.equals(that.sellOrderId);
        }

        @Override
        public int hashCode()
        {
            return Objects.hash(sequenceNumber, buyOrderId, sellOrderId, price, quantity);
        }

        @Override
        public String toString()
        {
            return "TradeExecuted[sequenceNumber=" + sequenceNumber +
                ", buyOrderId=" + buyOrderId +
                ", sellOrderId=" + sellOrderId +
                ", price=" + price +
                ", quantity=" + quantity + "]";
        }
    }

    final class OrderCancelled implements TradingEvent
    {
        private final long sequenceNumber;
        private final String orderId;

        public OrderCancelled(final long sequenceNumber, final String orderId)
        {
            this.sequenceNumber = sequenceNumber;
            this.orderId = Objects.requireNonNull(orderId, "orderId");
        }

        @Override
        public long getSequenceNumber()
        {
            return sequenceNumber;
        }

        public String getOrderId()
        {
            return orderId;
        }

        @Override
        public boolean equals(final Object other)
        {
            if (this == other)
            {
                return true;
            }
            if (!(other instanceof OrderCancelled))
            {
                return false;
            }
            final OrderCancelled that = (OrderCancelled)other;
            return sequenceNumber == that.sequenceNumber && orderId.equals(that.orderId);
        }

        @Override
        public int hashCode()
        {
            return Objects.hash(sequenceNumber, orderId);
        }

        @Override
        public String toString()
        {
            return "OrderCancelled[sequenceNumber=" + sequenceNumber + ", orderId=" + orderId + "]";
        }
    }
}
