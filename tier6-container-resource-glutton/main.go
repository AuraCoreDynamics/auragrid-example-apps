package main

import (
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	fmt.Println("Tier 6 Resource Glutton initialized. Commencing boundary breach...")

	// Spawn 4 CPU-intensive goroutines
	for i := 0; i < 4; i++ {
		go func(id int) {
			for {
				// Tight loop to consume CPU
				_ = id * id
			}
		}(i)
	}

	// Allocate 32MB of unmanaged heap every 100ms
	var allocations [][]byte
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	// Wait for termination signal
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)

	for {
		select {
		case <-ticker.C:
			// 32MB allocation
			chunk := make([]byte, 32*1024*1024)
			for j := range chunk {
				chunk[j] = 1 // Prevent optimization
			}
			allocations = append(allocations, chunk)
			
			totalMB := len(allocations) * 32
			fmt.Printf("Allocated 32MB chunk. Total: %d MB\n", totalMB)
			
			if totalMB >= 512 {
				fmt.Println("Reached 512MB limit, pausing allocations.")
				ticker.Stop()
			}
		case sig := <-sigs:
			fmt.Printf("Received signal: %v, exiting.\n", sig)
			os.Exit(0)
		}
	}
}
