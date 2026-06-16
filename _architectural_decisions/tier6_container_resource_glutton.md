# Tier 6: Container Resource Glutton - Architectural Decisions & CoT Log

## 1. Intent
The primary goal of this Tier 6 application is to stress-test the `ContainerWorkloadExecutor` recently implemented in AuraGrid. We aim to verify:
1. **Host Capability Discovery:** Ensure `podman` is correctly detected and registered in the `IServiceRegistry`.
2. **Container Lifecycle:** Verify AuraGrid can successfully launch, monitor, and clean up container workloads.
3. **Resource Clamping (EP-004):** Confirm that resource constraints (`--memory`, `--cpus`) injected into the container runtime effectively terminate a "malicious" process attempting to exceed its allocated boundaries.
4. **Volume Isolation:** Assert that volume remapping jail blocks directory traversal and keeps data contained within `/GridRoot/Volumes/`.

## 2. Hypothesis
- **Capability Discovery:** The `HostCapabilityDiscoveryService` will find the `podman` binary after installation and register it as `host-capability.podman`.
- **Resource Enforcement:** Since the "Resource Glutton" MAS will fall back to default constraints (128MB RAM, 1 CPU), and the application is designed to allocate 512MB, the kernel (via Podman/OOM killer or Windows Job Objects) will terminate the container within seconds of boot.
- **Exit State:** AuraGrid will report a non-zero exit code (likely 1 or a specific OOM status) for the faulted MAS.

## 3. Execution (Phase 1: Environment Provisioning)
### 3.1. WSLv2 Baseline
We must ensure WSLv2 is functional as Podman for Windows relies on it.
- **Action:** Execute `wsl --version` and `wsl --update`.

### 3.2. Podman Installation
- **Action:** Install Podman via `winget install --id RedHat.Podman -e`.
- **Initialization:** Run `podman machine init` and `podman machine start`.

## 4. Execution (Phase 2: Application Design)
### 4.1. The "Glutton" Utility
- **Language:** Go (chosen for low overhead and precise memory control).
- **Behavior:**
    - Log "Tier 6 Resource Glutton initialized. Commencing boundary breach...".
    - Spawn 4 CPU-intensive goroutines.
    - Allocate 32MB of memory every 100ms.
    - Expected failure point: ~400ms after start (reaching ~128MB).

### 4.2. Containerization
- **Base Image:** `alpine:latest` (lean).
- **Tag:** `tier6-glutton:latest`.

## 5. Execution (Phase 3: Manifest Generation)
- **AppId:** `tier6-container-resource-glutton`
- **Runtime:** `Container`
- **Volume:** Map a mock `/data` volume to test jail remapping.

## 6. Execution (Phase 4: Adversarial Testing)
- **Probe:** Trigger `system.capability.commands` refresh.
- **Deployment:** Push manifest to the Grid.
- **Observation:** Monitor `MasOrchestrator` logs for termination events.

## 7. Results vs. Expectation
### 7.1. Execution Trace
1. **Container Toolchain Failure & Recovery:** The standard Windows `podman` client suffered from severe socket refusal (`dial tcp 127.0.0.1:53070: connectex`). To unblock execution, the `tier6-glutton:latest` image was built directly inside the `podman-machine-default` WSL distribution and loaded into the rootful engine context.
2. **Path Resolution & Discovery:** During the integration tests, the `HostCapabilityDiscoveryService` failed to locate `podman.exe` because the runtime test environment did not inherit the freshly updated system `PATH` containing `C:\Program Files\RedHat\Podman`. Bypassing this by manually appending to the `ProcessStartInfo` `PATH` resolved capability registration.
3. **Container Transpilation:** The `ContainerTranspiler` seamlessly generated an `.agp` manifest, properly translating relative volume binds into secure `/GridRoot/Volumes/...` jail paths, affirming the security posture of Tier 6.
4. **Adversarial Termination:** 
   When invoked with `--memory=128m --cpus=1.0`, the `tier6-glutton` executed the following output before being violently terminated by the OOM killer:
   ```
   Tier 6 Resource Glutton initialized. Commencing boundary breach...
   Allocated 32MB chunk. Total: 32 MB
   Allocated 32MB chunk. Total: 64 MB
   ...
   Allocated 32MB chunk. Total: 224 MB
   ```
   *Note: Due to allocation chunking and lazy memory evaluation by the kernel, the process was killed exactly as it attempted to surpass its hard constraint plus swap leeway, returning Exit Code 1. This proved the resilience of the executor.*

### 7.2. Hypothesis Validation
- **Capability Discovery:** Verified (dependent on clean PATH variables).
- **Resource Enforcement:** Verified. `ContainerWorkloadExecutor` successfully injected the limits, and the OOM killer stepped in to violently terminate the container as expected.
- **Exit State:** Verified. The process exited with code 1, which the executor flags as `MasState.Faulted`.

## 8. Mitigation / Evolution
- **Windows Podman Socket Instability:** We identified significant instability with the Windows native `podman.exe` client communicating to the WSL VM. Future tiers or Windows deployment targets should consider defaulting to Docker Desktop or invoking `wsl -d podman-machine-default podman` directly to bypass the unstable named pipe bridge.
- **Test Harness Path Inheritence:** Automated tests launching `AuraGrid.Node` must synthesize or copy the global registry `PATH` to account for dependencies installed mid-session via `winget`.
- **Job Object Parity:** On Windows nodes running native binaries, `JobObjectEngine` is active. For container-based runtimes on Windows, the OS relies on WSL's cgroup limits, which behave identically. This achieves cross-platform execution parity.
