package dev.playground.replaylab.phase3;

import dev.playground.replaylab.codec.TradingEventCodec;
import dev.playground.replaylab.model.TradingEvent;
import io.aeron.Aeron;
import io.aeron.ExclusivePublication;
import io.aeron.Publication;
import io.aeron.archive.client.AeronArchive;
import io.aeron.archive.status.RecordingPos;
import org.agrona.concurrent.UnsafeBuffer;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.LockSupport;
import java.util.function.BooleanSupplier;

final class Phase3ProcessSupport
{
    static final String LIVE_CHANNEL = "aeron:ipc";
    static final String REPLAY_CHANNEL = "aeron:ipc";
    static final String ARCHIVE_CONTROL_CHANNEL = "aeron:ipc?term-length=64k";
    static final int LIVE_STREAM_ID = 30_001;
    static final int REPLAY_STREAM_ID = 30_002;
    static final int ARCHIVE_CONTROL_STREAM_ID = 30_003;
    static final int ARCHIVE_CONTROL_RESPONSE_STREAM_ID = 30_004;
    static final int REPLAY_PREFIX_EVENT_COUNT = 4;
    static final int TOTAL_EVENT_COUNT = 6;
    static final Duration OPERATION_TIMEOUT = Duration.ofSeconds(20);
    static final String MANIFEST_FILE = "phase3.properties";

    private Phase3ProcessSupport()
    {
    }

    static Path runDirectory(final String[] args)
    {
        if (args.length != 1)
        {
            throw new IllegalArgumentException("Expected one argument: the shared Phase 3 run directory");
        }
        return Path.of(args[0]).toAbsolutePath();
    }

    static Aeron connectAeron(final Path runDirectory)
    {
        return Aeron.connect(new Aeron.Context()
            .aeronDirectoryName(runDirectory.resolve("media-driver").toString()));
    }

    static AeronArchive connectArchive(final Aeron aeron)
    {
        return AeronArchive.connect(new AeronArchive.Context()
            .controlRequestChannel(ARCHIVE_CONTROL_CHANNEL)
            .controlRequestStreamId(ARCHIVE_CONTROL_STREAM_ID)
            .controlResponseChannel(ARCHIVE_CONTROL_CHANNEL)
            .controlResponseStreamId(ARCHIVE_CONTROL_RESPONSE_STREAM_ID)
            .aeron(aeron));
    }

    static List<TradingEvent> demoEvents()
    {
        return List.of(
            new TradingEvent.OrderPlaced(1, "B-1001", TradingEvent.Side.BUY, 101, 10),
            new TradingEvent.OrderPlaced(2, "S-2001", TradingEvent.Side.SELL, 100, 6),
            new TradingEvent.TradeExecuted(3, "B-1001", "S-2001", 100, 4),
            new TradingEvent.OrderCancelled(4, "S-2001"),
            new TradingEvent.OrderPlaced(5, "S-2002", TradingEvent.Side.SELL, 101, 3),
            new TradingEvent.TradeExecuted(6, "B-1001", "S-2002", 101, 3));
    }

    static TradingEvent decode(final org.agrona.DirectBuffer buffer, final int offset, final int length)
    {
        final byte[] payload = new byte[length];
        buffer.getBytes(offset, payload);
        try
        {
            return TradingEventCodec.decode(payload);
        }
        catch (final IOException exception)
        {
            throw new IllegalStateException("Could not decode an Aeron event", exception);
        }
    }

    static void publish(final ExclusivePublication publication, final TradingEvent event)
    {
        final byte[] payload;
        try
        {
            payload = TradingEventCodec.encode(event);
        }
        catch (final IOException exception)
        {
            throw new IllegalStateException("Could not encode a trading event", exception);
        }

        final UnsafeBuffer buffer = new UnsafeBuffer(payload);
        final long deadline = System.nanoTime() + OPERATION_TIMEOUT.toNanos();
        while (true)
        {
            final long result = publication.offer(buffer, 0, payload.length);
            if (result >= 0)
            {
                System.out.println("PUBLISHED sequenceNumber=" + event.getSequenceNumber() +
                    " position=" + result);
                return;
            }
            if (result != Publication.BACK_PRESSURED &&
                result != Publication.ADMIN_ACTION &&
                result != Publication.NOT_CONNECTED)
            {
                throw new IllegalStateException("Could not publish event " + event.getSequenceNumber() +
                    ": " + Publication.errorString(result));
            }
            if (System.nanoTime() >= deadline)
            {
                throw new IllegalStateException("Timed out publishing event " + event.getSequenceNumber());
            }
            LockSupport.parkNanos(100_000);
        }
    }

    static long awaitRecordingPosition(
        final Aeron aeron,
        final AeronArchive archive,
        final ExclusivePublication publication)
    {
        final long expectedPosition = publication.position();
        final int[] counterId = { -1 };
        final long[] archivePosition = { -1 };
        await(() ->
        {
            final int foundCounterId = RecordingPos.findCounterIdBySession(
                aeron.countersReader(), publication.sessionId(), archive.archiveId());
            if (foundCounterId < 0)
            {
                return false;
            }
            counterId[0] = foundCounterId;
            archivePosition[0] = aeron.countersReader().getCounterValue(foundCounterId);
            return archivePosition[0] >= expectedPosition;
        }, "Archive to record through publication position " + expectedPosition);
        System.out.println("ARCHIVE_CAUGHT_UP position=" + archivePosition[0] +
            " counterId=" + counterId[0]);
        return archivePosition[0];
    }

    static long awaitRecordingId(final AeronArchive archive)
    {
        final AtomicLong recordingId = new AtomicLong(-1);
        await(() ->
        {
            recordingId.set(-1);
            final int count = archive.listRecordingsForUri(
                0,
                100,
                LIVE_CHANNEL,
                LIVE_STREAM_ID,
                (controlSessionId, correlationId, foundRecordingId, startTimestamp, stopTimestamp,
                 startPosition, stopPosition, initialTermId, segmentFileLength, termBufferLength,
                 mtuLength, sessionId, streamId, strippedChannel, originalChannel, sourceIdentity) ->
                    recordingId.set(foundRecordingId));
            return count == 1 && recordingId.get() >= 0;
        }, "Archive catalog to create the live recording descriptor");
        return recordingId.get();
    }

    static long getLong(final Properties properties, final String key)
    {
        final String value = properties.getProperty(key);
        if (value == null)
        {
            throw new IllegalStateException("Missing Phase 3 manifest field: " + key);
        }
        return Long.parseLong(value);
    }

    static Properties readManifest(final Path runDirectory) throws IOException
    {
        final Properties properties = new Properties();
        try (var input = Files.newInputStream(runDirectory.resolve(MANIFEST_FILE)))
        {
            properties.load(input);
        }
        return properties;
    }

    static void writeManifest(final Path runDirectory, final Properties properties) throws IOException
    {
        try (var output = Files.newOutputStream(runDirectory.resolve(MANIFEST_FILE)))
        {
            properties.store(output, "Phase 3 recording and replay boundary");
        }
    }

    static void writeMarker(final Path runDirectory, final String marker) throws IOException
    {
        Files.writeString(runDirectory.resolve(marker), Long.toString(ProcessHandle.current().pid()));
        System.out.println("MARKER_WRITTEN=" + marker);
    }

    static void awaitMarker(final Path runDirectory, final String marker, final Duration timeout)
    {
        final Path markerPath = runDirectory.resolve(marker);
        await(() -> Files.exists(markerPath), "marker " + marker, timeout);
    }

    static void await(final BooleanSupplier condition, final String operation)
    {
        await(condition, operation, OPERATION_TIMEOUT);
    }

    static void await(final BooleanSupplier condition, final String operation, final Duration timeout)
    {
        final long deadline = System.nanoTime() + timeout.toNanos();
        while (!condition.getAsBoolean())
        {
            if (System.nanoTime() >= deadline)
            {
                throw new IllegalStateException("Timed out waiting for " + operation);
            }
            LockSupport.parkNanos(1_000_000);
        }
    }
}
