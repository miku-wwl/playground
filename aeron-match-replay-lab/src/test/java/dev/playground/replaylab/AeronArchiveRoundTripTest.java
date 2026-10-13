package dev.playground.replaylab;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AeronArchiveRoundTripTest
{
    @Test
    @Timeout(value = 45, unit = TimeUnit.SECONDS)
    void recordsAndReplaysEveryTradingEventInOrder(@TempDir final Path tempDir) throws Exception
    {
        final List<TradingEvent> events = TradingReplayDemo.demoEvents();

        final ReplayService.Result result = new ReplayService(tempDir).recordReplayAndVerify(events);

        assertEquals(events, result.getReplayedEvents());
        assertEquals(events.size(), result.getReplayedEvents().size());
        assertEquals(
            result.getRecording().getPublicationStopPosition(),
            result.getRecording().getArchiveRecordedPosition());
        assertTrue(result.getRecording().getRecordingId() >= 0);
        assertEquals(6, result.getReconstructedState().getLastProcessedSequenceNumber());
    }
}
