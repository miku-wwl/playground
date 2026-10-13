package dev.playground.replaylab.gateway;

import dev.playground.replaylab.codec.TradingEventCodec;
import dev.playground.replaylab.model.TradingEvent;
import io.aeron.Aeron;
import io.aeron.ChannelUri;
import io.aeron.ExclusivePublication;
import io.aeron.Publication;
import io.aeron.Subscription;
import io.aeron.archive.Archive;
import io.aeron.archive.ArchivingMediaDriver;
import io.aeron.archive.client.AeronArchive;
import io.aeron.archive.codecs.SourceLocation;
import io.aeron.archive.status.RecordingPos;
import io.aeron.driver.MediaDriver;
import org.agrona.concurrent.UnsafeBuffer;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.LockSupport;
import java.util.function.BooleanSupplier;

/** Owns one application's real Aeron and Aeron Archive connections. */
@Component
public final class AeronArchiveGateway implements AutoCloseable, DisposableBean
{
    private static final String LIVE_CHANNEL = "aeron:ipc";
    private static final String REPLAY_CHANNEL = "aeron:ipc";
    private static final String ARCHIVE_CONTROL_CHANNEL = "aeron:ipc?term-length=64k";
    private static final String ARCHIVE_REPLICATION_CHANNEL = "aeron:udp?endpoint=localhost:0";
    private static final int FIRST_REQUEST_STREAM_ID = 20_001;
    private static final int ARCHIVE_CONTROL_STREAM_ID = 10_003;
    private static final int ARCHIVE_CONTROL_RESPONSE_STREAM_ID = 10_004;
    private static final Duration OPERATION_TIMEOUT = Duration.ofSeconds(15);
    private static final int MAX_REPLAY_FRAGMENTS_PER_POLL = 16;

    private final Path archiveDirectory;
    private final AtomicInteger nextStreamId = new AtomicInteger(FIRST_REQUEST_STREAM_ID);
    private ArchivingMediaDriver archivingMediaDriver;
    private Aeron aeron;
    private AeronArchive archive;
    private volatile boolean closed;

    @Autowired
    public AeronArchiveGateway() throws IOException
    {
        this(Path.of("target", "aeron-phase2-runs"));
    }

    public AeronArchiveGateway(final Path outputDirectory) throws IOException
    {
        Files.createDirectories(outputDirectory);
        final Path runDirectory = Files.createTempDirectory(outputDirectory, "run-");
        final Path mediaDriverDirectory = runDirectory.resolve("media-driver");
        archiveDirectory = runDirectory.resolve("archive");
        Files.createDirectories(archiveDirectory);

        try
        {
            archivingMediaDriver = ArchivingMediaDriver.launch(
                new MediaDriver.Context()
                    .aeronDirectoryName(mediaDriverDirectory.toString())
                    .dirDeleteOnStart(true),
                new Archive.Context()
                    .aeronDirectoryName(mediaDriverDirectory.toString())
                    .archiveDirectoryName(archiveDirectory.toString())
                    .controlChannelEnabled(false)
                    .localControlChannel(ARCHIVE_CONTROL_CHANNEL)
                    .localControlStreamId(ARCHIVE_CONTROL_STREAM_ID)
                    .replicationChannel(ARCHIVE_REPLICATION_CHANNEL)
                    .archiveClientContext(new AeronArchive.Context()
                        .controlResponseChannel(ARCHIVE_CONTROL_CHANNEL)
                        .controlResponseStreamId(ARCHIVE_CONTROL_RESPONSE_STREAM_ID))
                    .deleteArchiveOnStart(false));
            aeron = Aeron.connect(
                new Aeron.Context().aeronDirectoryName(mediaDriverDirectory.toString()));
            archive = AeronArchive.connect(new AeronArchive.Context()
                .controlRequestChannel(ARCHIVE_CONTROL_CHANNEL)
                .controlRequestStreamId(ARCHIVE_CONTROL_STREAM_ID)
                .controlResponseChannel(ARCHIVE_CONTROL_CHANNEL)
                .controlResponseStreamId(ARCHIVE_CONTROL_RESPONSE_STREAM_ID)
                .aeron(aeron));

            System.out.println("ARCHIVE_DIRECTORY=" + archiveDirectory.toAbsolutePath());
            System.out.println("MEDIA_DRIVER_ARCHIVE=STARTED (embedded)");
        }
        catch (final RuntimeException failure)
        {
            try
            {
                close();
            }
            catch (final RuntimeException closeFailure)
            {
                failure.addSuppressed(closeFailure);
            }
            throw failure;
        }
    }

    public Recording record(final List<TradingEvent> events) throws IOException
    {
        ensureOpen();
        final int liveStreamId = nextStreamId.getAndAdd(2);
        if (liveStreamId <= 0 || liveStreamId >= Integer.MAX_VALUE)
        {
            throw new IllegalStateException("No more request-specific Aeron stream IDs are available");
        }
        final int replayStreamId = liveStreamId + 1;
        final long recordingSubscriptionId =
            archive.startRecording(LIVE_CHANNEL, liveStreamId, SourceLocation.LOCAL);
        System.out.println("RECORDING_STARTED subscriptionId=" + recordingSubscriptionId +
            " channel=" + LIVE_CHANNEL + " streamId=" + liveStreamId);

        final long publicationStopPosition;
        final long archivePosition;
        try (ExclusivePublication publication = aeron.addExclusivePublication(LIVE_CHANNEL, liveStreamId))
        {
            await(publication::isConnected, "publication connection to Archive recording");
            System.out.println("PUBLICATION_CONNECTED sessionId=" + publication.sessionId());

            for (final TradingEvent event : events)
            {
                final byte[] payload = TradingEventCodec.encode(event);
                final UnsafeBuffer buffer = new UnsafeBuffer(payload);
                offerWithBackPressure(publication, buffer, payload.length, event.getSequenceNumber());
                System.out.println("PUBLISHED sequenceNumber=" + event.getSequenceNumber() +
                    " event=" + event.getClass().getSimpleName());
            }

            publicationStopPosition = publication.position();
            System.out.println("PUBLICATION_STOP_POSITION=" + publicationStopPosition);

            final long[] observedRecordingPosition = { -1 };
            final int[] recordingCounterId = { -1 };
            await(() ->
            {
                final int counterId = RecordingPos.findCounterIdBySession(
                    aeron.countersReader(), publication.sessionId(), archive.archiveId());
                if (counterId < 0)
                {
                    return false;
                }
                recordingCounterId[0] = counterId;
                observedRecordingPosition[0] = aeron.countersReader().getCounterValue(counterId);
                return observedRecordingPosition[0] >= publicationStopPosition;
            }, "Archive recording position to reach publication stop position");
            archivePosition = observedRecordingPosition[0];
            System.out.println("ARCHIVE_RECORDED_POSITION=" + archivePosition +
                " recordingCounterId=" + recordingCounterId[0]);
            archive.stopRecording(recordingSubscriptionId);
            System.out.println("RECORDING_STOPPED subscriptionId=" + recordingSubscriptionId);
        }

        final RecordingDescriptor descriptor = queryRecording(liveStreamId, publicationStopPosition);
        if (descriptor.getStopPosition() != publicationStopPosition)
        {
            throw new IllegalStateException(
                "Archive stop position " + descriptor.getStopPosition() +
                    " differs from publication position " + publicationStopPosition);
        }
        System.out.println("RECORDING_ID_QUERIED=" + descriptor.getRecordingId() +
            " startPosition=" + descriptor.getStartPosition() +
            " stopPosition=" + descriptor.getStopPosition());

        return new Recording(
            descriptor.getRecordingId(),
            descriptor.getStartPosition(),
            descriptor.getStopPosition(),
            publicationStopPosition,
            archivePosition,
            archiveDirectory,
            liveStreamId,
            replayStreamId);
    }

    public List<TradingEvent> replay(final Recording recording, final int expectedEventCount)
    {
        ensureOpen();
        final long replayLength = recording.getStopPosition() - recording.getStartPosition();
        final long replaySessionId = archive.startReplay(
            recording.getRecordingId(),
            recording.getStartPosition(),
            replayLength,
            REPLAY_CHANNEL,
            recording.getReplayStreamId());
        final String replaySessionChannel = ChannelUri.addSessionId(REPLAY_CHANNEL, (int)replaySessionId);
        System.out.println("REPLAY_STARTED recordingId=" + recording.getRecordingId() +
            " replaySessionId=" + replaySessionId +
            " channel=" + REPLAY_CHANNEL + " streamId=" + recording.getReplayStreamId());

        final List<TradingEvent> replayedEvents = new ArrayList<>(expectedEventCount);
        try (Subscription replaySubscription =
                 aeron.addSubscription(replaySessionChannel, recording.getReplayStreamId()))
        {
            await(replaySubscription::isConnected, "independent Archive replay subscription");
            System.out.println("REPLAY_SUBSCRIPTION_CONNECTED channel=" + replaySessionChannel +
                " streamId=" + recording.getReplayStreamId());

            final long deadline = System.nanoTime() + OPERATION_TIMEOUT.toNanos();
            while (replayedEvents.size() < expectedEventCount)
            {
                if (System.nanoTime() >= deadline)
                {
                    throw new IllegalStateException(
                        "Timed out replaying events: received " + replayedEvents.size() +
                            " of " + expectedEventCount);
                }

                final int remaining = expectedEventCount - replayedEvents.size();
                final int fragments = replaySubscription.poll((buffer, offset, length, header) ->
                {
                    final byte[] payload = new byte[length];
                    buffer.getBytes(offset, payload);
                    try
                    {
                        final TradingEvent event = TradingEventCodec.decode(payload);
                        replayedEvents.add(event);
                        System.out.println("REPLAYED sequenceNumber=" + event.getSequenceNumber() +
                            " event=" + event.getClass().getSimpleName());
                    }
                    catch (final IOException exception)
                    {
                        throw new IllegalStateException("Could not decode replayed event", exception);
                    }
                }, Math.min(MAX_REPLAY_FRAGMENTS_PER_POLL, remaining));

                if (fragments == 0)
                {
                    LockSupport.parkNanos(100_000);
                }
            }
        }
        return List.copyOf(replayedEvents);
    }

    private RecordingDescriptor queryRecording(final int liveStreamId, final long expectedStopPosition)
    {
        final long deadline = System.nanoTime() + OPERATION_TIMEOUT.toNanos();
        while (true)
        {
            final AtomicLong queriedId = new AtomicLong(-1);
            final AtomicLong startPosition = new AtomicLong(-1);
            final AtomicLong stopPosition = new AtomicLong(-1);
            final int recordingCount = archive.listRecordingsForUri(
                0,
                100,
                LIVE_CHANNEL,
                liveStreamId,
                (controlSessionId, correlationId, recordingId, startTimestamp, stopTimestamp,
                 descriptorStartPosition, descriptorStopPosition, initialTermId, segmentFileLength,
                 termBufferLength, mtuLength, sessionId, streamId, strippedChannel, originalChannel,
                 sourceIdentity) ->
                {
                    queriedId.set(recordingId);
                    startPosition.set(descriptorStartPosition);
                    stopPosition.set(descriptorStopPosition);
                });

            if (recordingCount != 1 || queriedId.get() < 0)
            {
                throw new IllegalStateException(
                    "Expected one matching Archive recording but found count=" + recordingCount +
                        ", id=" + queriedId.get());
            }
            if (stopPosition.get() == expectedStopPosition)
            {
                return new RecordingDescriptor(queriedId.get(), startPosition.get(), stopPosition.get());
            }
            if (stopPosition.get() >= 0)
            {
                throw new IllegalStateException(
                    "Archive stop position " + stopPosition.get() +
                        " differs from publication position " + expectedStopPosition);
            }
            if (System.nanoTime() >= deadline)
            {
                throw new IllegalStateException(
                    "Timed out waiting for Archive catalog stop position; expected=" + expectedStopPosition +
                        ", actual=" + stopPosition.get());
            }
            LockSupport.parkNanos(100_000);
        }
    }

    private void offerWithBackPressure(
        final ExclusivePublication publication,
        final UnsafeBuffer buffer,
        final int length,
        final long sequenceNumber)
    {
        final long deadline = System.nanoTime() + OPERATION_TIMEOUT.toNanos();
        while (true)
        {
            final long result = publication.offer(buffer, 0, length);
            if (result >= 0)
            {
                return;
            }
            if (result != Publication.BACK_PRESSURED &&
                result != Publication.ADMIN_ACTION &&
                result != Publication.NOT_CONNECTED)
            {
                throw new IllegalStateException(
                    "Publication offer failed for sequence " + sequenceNumber + ": " +
                        Publication.errorString(result));
            }
            if (System.nanoTime() >= deadline)
            {
                throw new IllegalStateException(
                    "Timed out publishing sequence " + sequenceNumber + ": " +
                        Publication.errorString(result));
            }
            LockSupport.parkNanos(100_000);
        }
    }

    private void await(final BooleanSupplier condition, final String operation)
    {
        final long deadline = System.nanoTime() + OPERATION_TIMEOUT.toNanos();
        while (!condition.getAsBoolean())
        {
            if (System.nanoTime() >= deadline)
            {
                throw new IllegalStateException("Timed out waiting for " + operation);
            }
            LockSupport.parkNanos(100_000);
        }
    }

    private void ensureOpen()
    {
        if (closed)
        {
            throw new IllegalStateException("Aeron Archive gateway is already closed");
        }
    }

    @Override
    public void close()
    {
        if (closed)
        {
            return;
        }
        closed = true;
        try
        {
            if (archive != null)
            {
                archive.close();
            }
        }
        finally
        {
            try
            {
                if (aeron != null)
                {
                    aeron.close();
                }
            }
            finally
            {
                if (archivingMediaDriver != null)
                {
                    archivingMediaDriver.close();
                }
            }
        }
    }

    @Override
    public void destroy()
    {
        close();
    }

    public static final class Recording
    {
        private final long recordingId;
        private final long startPosition;
        private final long stopPosition;
        private final long publicationStopPosition;
        private final long archiveRecordedPosition;
        private final Path archiveDirectory;
        private final int liveStreamId;
        private final int replayStreamId;

        Recording(
            final long recordingId,
            final long startPosition,
            final long stopPosition,
            final long publicationStopPosition,
            final long archiveRecordedPosition,
            final Path archiveDirectory,
            final int liveStreamId,
            final int replayStreamId)
        {
            this.recordingId = recordingId;
            this.startPosition = startPosition;
            this.stopPosition = stopPosition;
            this.publicationStopPosition = publicationStopPosition;
            this.archiveRecordedPosition = archiveRecordedPosition;
            this.archiveDirectory = archiveDirectory;
            this.liveStreamId = liveStreamId;
            this.replayStreamId = replayStreamId;
        }

        public long getRecordingId()
        {
            return recordingId;
        }

        public long getStartPosition()
        {
            return startPosition;
        }

        public long getStopPosition()
        {
            return stopPosition;
        }

        public long getPublicationStopPosition()
        {
            return publicationStopPosition;
        }

        public long getArchiveRecordedPosition()
        {
            return archiveRecordedPosition;
        }

        public Path getArchiveDirectory()
        {
            return archiveDirectory;
        }

        public int getLiveStreamId()
        {
            return liveStreamId;
        }

        public int getReplayStreamId()
        {
            return replayStreamId;
        }
    }

    private static final class RecordingDescriptor
    {
        private final long recordingId;
        private final long startPosition;
        private final long stopPosition;

        private RecordingDescriptor(
            final long recordingId,
            final long startPosition,
            final long stopPosition)
        {
            this.recordingId = recordingId;
            this.startPosition = startPosition;
            this.stopPosition = stopPosition;
        }

        private long getRecordingId()
        {
            return recordingId;
        }

        private long getStartPosition()
        {
            return startPosition;
        }

        private long getStopPosition()
        {
            return stopPosition;
        }
    }
}
