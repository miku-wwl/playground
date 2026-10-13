package dev.playground.replaylab.phase3;

import io.aeron.archive.Archive;
import io.aeron.archive.ArchivingMediaDriver;
import io.aeron.archive.client.AeronArchive;
import io.aeron.driver.MediaDriver;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

/** Standalone JVM process for the Phase 3 MediaDriver and Aeron Archive. */
public final class Phase3ArchiveProcess
{
    private Phase3ArchiveProcess()
    {
    }

    public static void main(final String[] args) throws Exception
    {
        final Path runDirectory = Phase3ProcessSupport.runDirectory(args);
        final Path mediaDriverDirectory = runDirectory.resolve("media-driver");
        final Path archiveDirectory = runDirectory.resolve("archive");
        Files.createDirectories(mediaDriverDirectory);
        Files.createDirectories(archiveDirectory);

        try (ArchivingMediaDriver ignored = ArchivingMediaDriver.launch(
            new MediaDriver.Context()
                .aeronDirectoryName(mediaDriverDirectory.toString())
                .dirDeleteOnStart(false),
            new Archive.Context()
                .aeronDirectoryName(mediaDriverDirectory.toString())
                .archiveDirectoryName(archiveDirectory.toString())
                .controlChannelEnabled(false)
                .localControlChannel(Phase3ProcessSupport.ARCHIVE_CONTROL_CHANNEL)
                .localControlStreamId(Phase3ProcessSupport.ARCHIVE_CONTROL_STREAM_ID)
                .replicationChannel("aeron:udp?endpoint=localhost:0")
                .archiveClientContext(new AeronArchive.Context()
                    .controlResponseChannel(Phase3ProcessSupport.ARCHIVE_CONTROL_CHANNEL)
                    .controlResponseStreamId(Phase3ProcessSupport.ARCHIVE_CONTROL_RESPONSE_STREAM_ID))
                .deleteArchiveOnStart(false)))
        {
            System.out.println("ARCHIVE_PROCESS_PID=" + ProcessHandle.current().pid());
            System.out.println("MEDIA_DRIVER_ARCHIVE=STARTED (separate JVM)");
            System.out.println("ARCHIVE_DIRECTORY=" + archiveDirectory.toAbsolutePath());
            Phase3ProcessSupport.writeMarker(runDirectory, "archive.ready");
            Phase3ProcessSupport.awaitMarker(runDirectory, "archive.stop", Duration.ofMinutes(2));
            System.out.println("ARCHIVE_PROCESS_STOPPING");
        }
    }
}
