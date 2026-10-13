package dev.playground.replaylab.phase3;

import dev.playground.replaylab.model.TradingEvent;
import io.aeron.Aeron;
import io.aeron.ExclusivePublication;
import io.aeron.archive.client.AeronArchive;
import io.aeron.archive.codecs.SourceLocation;

import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Properties;

/** Publishes two batches while the consumer is stopped and recovering. */
public final class Phase3PublisherProcess
{
    private Phase3PublisherProcess()
    {
    }

    public static void main(final String[] args) throws Exception
    {
        final Path runDirectory = Phase3ProcessSupport.runDirectory(args);
        final List<TradingEvent> events = Phase3ProcessSupport.demoEvents();

        try (Aeron aeron = Phase3ProcessSupport.connectAeron(runDirectory);
             AeronArchive archive = Phase3ProcessSupport.connectArchive(aeron))
        {
            final long recordingSubscriptionId = archive.startRecording(
                Phase3ProcessSupport.LIVE_CHANNEL,
                Phase3ProcessSupport.LIVE_STREAM_ID,
                SourceLocation.LOCAL);
            System.out.println("PUBLISHER_PROCESS_PID=" + ProcessHandle.current().pid());
            System.out.println("RECORDING_STARTED subscriptionId=" + recordingSubscriptionId +
                " streamId=" + Phase3ProcessSupport.LIVE_STREAM_ID);

            try (ExclusivePublication publication = aeron.addExclusivePublication(
                Phase3ProcessSupport.LIVE_CHANNEL,
                Phase3ProcessSupport.LIVE_STREAM_ID))
            {
                Phase3ProcessSupport.await(publication::isConnected, "publisher connection to Archive");
                Phase3ProcessSupport.awaitMarker(runDirectory, "consumer.initial.ready", Duration.ofSeconds(30));
                publishBatch(publication, events, 0, 2);
                Phase3ProcessSupport.awaitRecordingPosition(aeron, archive, publication);

                final long recordingId = Phase3ProcessSupport.awaitRecordingId(archive);
                final Properties manifest = new Properties();
                manifest.setProperty("recordingId", Long.toString(recordingId));
                manifest.setProperty("liveStreamId", Integer.toString(Phase3ProcessSupport.LIVE_STREAM_ID));
                manifest.setProperty("replayStreamId", Integer.toString(Phase3ProcessSupport.REPLAY_STREAM_ID));
                manifest.setProperty("recordingStartPosition", Long.toString(archive.getStartPosition(recordingId)));
                Phase3ProcessSupport.writeManifest(runDirectory, manifest);
                System.out.println("RECORDING_ID=" + recordingId);

                Phase3ProcessSupport.awaitMarker(runDirectory, "consumer.initial.done", Duration.ofSeconds(30));
                publishBatch(publication, events, 2, 4);
                final long replayBoundary = Phase3ProcessSupport.awaitRecordingPosition(aeron, archive, publication);
                manifest.setProperty("replayBoundaryPosition", Long.toString(replayBoundary));
                manifest.setProperty("replayPrefixEvents", Integer.toString(
                    Phase3ProcessSupport.REPLAY_PREFIX_EVENT_COUNT));
                Phase3ProcessSupport.writeManifest(runDirectory, manifest);
                Phase3ProcessSupport.writeMarker(runDirectory, "publisher.replay-boundary.ready");

                Phase3ProcessSupport.awaitMarker(runDirectory, "consumer.recovery.ready", Duration.ofSeconds(30));
                publishBatch(publication, events, 4, events.size());
                Phase3ProcessSupport.awaitRecordingPosition(aeron, archive, publication);
                archive.stopRecording(recordingSubscriptionId);
                Phase3ProcessSupport.writeMarker(runDirectory, "publisher.done");
                System.out.println("PUBLISHER_FINISHED events=" + events.size());
            }
        }
    }

    private static void publishBatch(
        final ExclusivePublication publication,
        final List<TradingEvent> events,
        final int fromIndex,
        final int toIndex)
    {
        for (int index = fromIndex; index < toIndex; index++)
        {
            Phase3ProcessSupport.publish(publication, events.get(index));
        }
    }
}
