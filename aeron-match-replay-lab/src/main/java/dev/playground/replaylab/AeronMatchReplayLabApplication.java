package dev.playground.replaylab;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class AeronMatchReplayLabApplication
{
    public static void main(final String[] args)
    {
        SpringApplication.run(AeronMatchReplayLabApplication.class, args);
    }

    @Bean
    CommandLineRunner phaseZeroSummary()
    {
        return args -> {
            System.out.println("Aeron Match Replay Lab");
            System.out.println("Phase: 0 - environment and architecture");
            System.out.println("Java runtime: " + Runtime.version());
        };
    }
}
