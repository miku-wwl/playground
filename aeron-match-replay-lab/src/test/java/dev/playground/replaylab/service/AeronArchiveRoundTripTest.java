package dev.playground.replaylab.service;

import dev.playground.replaylab.controller.TradingReplayDemo;
import dev.playground.replaylab.gateway.AeronArchiveGateway;
import dev.playground.replaylab.model.TradingEvent;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
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

        final ReplayService.Result result;
        try (AeronArchiveGateway gateway = new AeronArchiveGateway(tempDir))
        {
            result = new ReplayService(gateway).recordReplayAndVerify(events);
        }

        assertEquals(events, result.getReplayedEvents());
        assertEquals(events.size(), result.getReplayedEvents().size());
        assertEquals(events.size(), result.getPublishedEvents());
        assertTrue(result.isStateMatched());
        assertEquals(result.getPublicationStopPosition(), result.getArchiveRecordedPosition());
        assertTrue(result.getRecordingId() >= 0);
        assertEquals(6, result.getReconstructedState().getLastProcessedSequenceNumber());
    }

    @Test
    @Timeout(value = 45, unit = TimeUnit.SECONDS)
    void serializesConcurrentRoundTripsAndKeepsTheirRecordingsSeparate(@TempDir final Path tempDir)
        throws Exception
    {
        final List<TradingEvent> events = TradingReplayDemo.demoEvents();
        try (AeronArchiveGateway gateway = new AeronArchiveGateway(tempDir))
        {
            final ReplayService service = new ReplayService(gateway);
            final ExecutorService executor = Executors.newFixedThreadPool(2);
            try
            {
                final List<Callable<ReplayService.Result>> requests = List.of(
                    () -> service.recordReplayAndVerify(events),
                    () -> service.recordReplayAndVerify(events));
                final List<Future<ReplayService.Result>> responses = executor.invokeAll(requests);
                final ReplayService.Result first = responses.get(0).get();
                final ReplayService.Result second = responses.get(1).get();

                assertTrue(first.isStateMatched());
                assertTrue(second.isStateMatched());
                assertEquals(events.size(), first.getReplayedEventCount());
                assertEquals(events.size(), second.getReplayedEventCount());
                assertTrue(first.getRecordingId() != second.getRecordingId());
            }
            finally
            {
                executor.shutdownNow();
            }
        }
    }
}
