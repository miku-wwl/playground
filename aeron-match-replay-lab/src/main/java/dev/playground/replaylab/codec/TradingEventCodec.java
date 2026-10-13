package dev.playground.replaylab.codec;

import dev.playground.replaylab.model.TradingEvent;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;

public final class TradingEventCodec
{
    private static final int ORDER_PLACED = 1;
    private static final int TRADE_EXECUTED = 2;
    private static final int ORDER_CANCELLED = 3;

    private TradingEventCodec()
    {
    }

    public static byte[] encode(final TradingEvent event) throws IOException
    {
        final ByteArrayOutputStream bytes = new ByteArrayOutputStream(96);
        try (DataOutputStream output = new DataOutputStream(bytes))
        {
            if (event instanceof TradingEvent.OrderPlaced)
            {
                final TradingEvent.OrderPlaced placed = (TradingEvent.OrderPlaced)event;
                output.writeByte(ORDER_PLACED);
                output.writeLong(placed.getSequenceNumber());
                output.writeUTF(placed.getOrderId());
                output.writeByte(placed.getSide().ordinal());
                output.writeLong(placed.getPrice());
                output.writeLong(placed.getQuantity());
            }
            else if (event instanceof TradingEvent.TradeExecuted)
            {
                final TradingEvent.TradeExecuted trade = (TradingEvent.TradeExecuted)event;
                output.writeByte(TRADE_EXECUTED);
                output.writeLong(trade.getSequenceNumber());
                output.writeUTF(trade.getBuyOrderId());
                output.writeUTF(trade.getSellOrderId());
                output.writeLong(trade.getPrice());
                output.writeLong(trade.getQuantity());
            }
            else if (event instanceof TradingEvent.OrderCancelled)
            {
                final TradingEvent.OrderCancelled cancelled = (TradingEvent.OrderCancelled)event;
                output.writeByte(ORDER_CANCELLED);
                output.writeLong(cancelled.getSequenceNumber());
                output.writeUTF(cancelled.getOrderId());
            }
            else
            {
                throw new IllegalArgumentException("Unsupported event type: " + event.getClass().getName());
            }
        }
        return bytes.toByteArray();
    }

    public static TradingEvent decode(final byte[] encoded) throws IOException
    {
        try (DataInputStream input = new DataInputStream(new ByteArrayInputStream(encoded)))
        {
            final int type = input.readUnsignedByte();
            final long sequenceNumber = input.readLong();
            final TradingEvent event;

            switch (type)
            {
                case ORDER_PLACED:
                {
                    final String orderId = input.readUTF();
                    final int sideCode = input.readUnsignedByte();
                    if (sideCode >= TradingEvent.Side.values().length)
                    {
                        throw new IOException("Unknown side code: " + sideCode);
                    }
                    event = new TradingEvent.OrderPlaced(
                        sequenceNumber,
                        orderId,
                        TradingEvent.Side.values()[sideCode],
                        input.readLong(),
                        input.readLong());
                    break;
                }
                case TRADE_EXECUTED:
                    event = new TradingEvent.TradeExecuted(
                        sequenceNumber,
                        input.readUTF(),
                        input.readUTF(),
                        input.readLong(),
                        input.readLong());
                    break;
                case ORDER_CANCELLED:
                    event = new TradingEvent.OrderCancelled(sequenceNumber, input.readUTF());
                    break;
                default:
                    throw new IOException("Unknown event type code: " + type);
            }

            if (input.available() != 0)
            {
                throw new IOException("Event contains trailing bytes: " + input.available());
            }
            return event;
        }
    }
}
