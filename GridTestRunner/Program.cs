using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace GridTestRunner;

class Program
{
    // ── Grid endpoint ────────────────────────────────────────────────────────────
    const string GridBase    = "https://127.0.0.1:7087";
    const string GridIpcBase = "https://127.0.0.1:8088";

    static string? s_clientCertPath;
    static string? s_clientCertPassword;
    static string? s_ipcToken;

    // ── All apps to deploy, with optional post-deploy smoke runners ──────────────
    static readonly AppEntry[] Apps =
    {
        new AppEntry("tier1-sovereign-beacon",          AppKind.Python),
        new AppEntry("grid-gauntlet-provocateur",       AppKind.Python),
        new AppEntry("grid-gauntlet-sentinel",          AppKind.Python),
        new AppEntry("tier3-sovereign-ledger",          AppKind.Python),
        new AppEntry("tier4-cognitive-beacon",          AppKind.Python),
        new AppEntry("tier4-model-foundry",             AppKind.Python),
        new AppEntry("tier4-telemetry-torrent",         AppKind.DotNet, @"C:\projects\auracore\app-examples\tier4-telemetry-torrent\src\TorrentClient\bin\Debug\net10.0\TorrentClient.exe"),
        new AppEntry("tier4-direct-inference-bypass",   AppKind.DotNet, @"C:\projects\auracore\app-examples\tier4-direct-inference-bypass\src\OrchestratorMas\bin\Debug\net10.0\OrchestratorMas.exe"),
        new AppEntry("tier5-entropy-engine",            AppKind.Python),
        new AppEntry("tier5-signed-chat",               AppKind.Python),
        new AppEntry("tier6-container-resource-glutton",AppKind.Python),
    };

    static async Task Main(string[] args)
    {
        s_ipcToken = Environment.GetEnvironmentVariable("AURAGRID_IPC_TOKEN") ?? "test-token";

        // ── Load PKI cert ─────────────────────────────────────────────────────────
        var certPath = @"C:\tmp\grid-smoke-test\certs\node.pem";
        var keyPath  = @"C:\tmp\grid-smoke-test\certs\node.key";

        X509Certificate2? clientCert = null;
        if (File.Exists(certPath) && File.Exists(keyPath))
        {
            try
            {
                var certPem         = await File.ReadAllTextAsync(certPath);
                var keyPemProtected = await File.ReadAllTextAsync(keyPath);
                var entropy         = "AuraGrid-Node-Identity"u8.ToArray();
                var bytes           = Convert.FromBase64String(keyPemProtected);
                var decrypted       = ProtectedData.Unprotect(bytes, entropy, DataProtectionScope.LocalMachine);
                var keyPem          = Encoding.UTF8.GetString(decrypted);

                using var rsa = RSA.Create();
                rsa.ImportFromPem(keyPem);
                var cert        = X509Certificate2.CreateFromPem(certPem);
                var certWithKey = cert.CopyWithPrivateKey(rsa);
                var pfxBytes    = certWithKey.Export(X509ContentType.Pfx, "runner-pfx");
                var tempPfx     = Path.Combine(Path.GetTempPath(), "grid-test-runner.pfx");
                await File.WriteAllBytesAsync(tempPfx, pfxBytes);
                clientCert = new X509Certificate2(tempPfx, "runner-pfx", X509KeyStorageFlags.PersistKeySet);
                s_clientCertPath = tempPfx;
                s_clientCertPassword = "runner-pfx";
                Console.WriteLine($"[PKI] Loaded client cert: {clientCert.Subject}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[PKI] Warning – could not load node cert ({ex.Message}). Proceeding without mTLS.");
            }
        }
        else
        {
            Console.WriteLine("[PKI] No node cert found – connecting without mTLS.");
        }

        var handler = new HttpClientHandler
        {
            ClientCertificateOptions = ClientCertificateOption.Manual,
            ServerCertificateCustomValidationCallback = (_, _, _, _) => true,
        };
        if (clientCert is not null)
            handler.ClientCertificates.Add(clientCert);

        using var client = new HttpClient(handler) { BaseAddress = new Uri(GridBase) };

        // ── Phase 1: Deploy all apps ───────────────────────────────────────────────
        Console.WriteLine("\n── Phase 1: Deploying all apps ──────────────────────────");
        var failed = new List<string>();
        foreach (var app in Apps)
        {
            Console.Write($"  [{app.Id,-42}] Deploying... ");
            var req = new { AppId = app.Id, Version = "1.0.0" };
            try
            {
                var response = await client.PostAsJsonAsync("/api/deployments", req);
                if (response.IsSuccessStatusCode)
                    Console.WriteLine("OK (202)");
                else
                {
                    var body = await response.Content.ReadAsStringAsync();
                    Console.WriteLine($"FAIL ({(int)response.StatusCode}) {body}");
                    failed.Add(app.Id);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"ERR: {ex.Message}");
                failed.Add(app.Id);
            }
        }

        // ── Phase 2: Wait for orchestrator to allocate ────────────────────────────
        Console.WriteLine("\n── Phase 2: Waiting 30 s for orchestrator allocation ────");
        await Task.Delay(30_000);

        // ── Phase 3: Verify via /api/deployments ─────────────────────────────────
        Console.WriteLine("\n── Phase 3: Verifying deployment records ────────────────");
        try
        {
            var deployResp = await client.GetAsync("/api/deployments");
            if (deployResp.IsSuccessStatusCode)
            {
                var body      = await deployResp.Content.ReadAsStringAsync();
                var doc       = JsonDocument.Parse(body);
                var deployedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                if (doc.RootElement.ValueKind == JsonValueKind.Array)
                    foreach (var el in doc.RootElement.EnumerateArray())
                        if (el.TryGetProperty("AppId", out var idProp) || el.TryGetProperty("appId", out idProp))
                            deployedIds.Add(idProp.GetString() ?? "");

                foreach (var app in Apps)
                {
                    bool found = deployedIds.Contains(app.Id);
                    Console.WriteLine($"  [{app.Id,-42}] {(found ? "REGISTERED ✓" : "NOT FOUND  ✗")}");
                }
            }
            else
            {
                Console.WriteLine($"  Could not query /api/deployments: {(int)deployResp.StatusCode}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"  ERR querying deployments: {ex.Message}");
        }

        // ── Phase 4: Query /api/services for running MAS instances ────────────────
        Console.WriteLine("\n── Phase 4: Querying live service instances ─────────────");
        try
        {
            var svcResp = await client.GetAsync("/api/services");
            if (svcResp.IsSuccessStatusCode)
            {
                var body = await svcResp.Content.ReadAsStringAsync();
                Console.WriteLine($"  /api/services response ({body.Length} bytes):");
                // Pretty-print first 2000 chars
                Console.WriteLine("  " + body[..Math.Min(body.Length, 2000)]);
            }
            else
            {
                Console.WriteLine($"  /api/services: {(int)svcResp.StatusCode}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"  ERR querying services: {ex.Message}");
        }

        // ── Phase 5: Run smoke executables for .NET apps ─────────────────────────
        Console.WriteLine("\n── Phase 5: Running .NET app smoke clients ───────────────");
        foreach (var app in Apps.Where(a => a.Kind == AppKind.DotNet && a.SmokeExe is not null))
        {
            Console.WriteLine($"\n  [{app.Id}]");
            if (!File.Exists(app.SmokeExe!))
            {
                Console.WriteLine($"    Smoke exe not built yet: {app.SmokeExe}");
                Console.WriteLine($"    Build with: dotnet build {Path.GetDirectoryName(app.SmokeExe)?.Replace("bin\\Debug\\net10.0", "")}");
                continue;
            }
            await ExecuteProcessAsync(app.SmokeExe!, "", label: app.Id, timeoutSeconds: 120);
        }

        // ── Summary ───────────────────────────────────────────────────────────────
        Console.WriteLine("\n══════════════════════════════════════════════════════════");
        Console.WriteLine("  GridTestRunner complete.");
        if (failed.Count > 0)
            Console.WriteLine($"  Deploy failures: {string.Join(", ", failed)}");
        else
            Console.WriteLine("  All deployments accepted by grid.");
        Console.WriteLine("══════════════════════════════════════════════════════════");
    }

    static async Task ExecuteProcessAsync(string exe, string args, string label = "", int timeoutSeconds = 60)
    {
        var psi = new System.Diagnostics.ProcessStartInfo(exe, args)
        {
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
        };
        psi.EnvironmentVariables["AURAGRID_PROXY_URL"] = "https://127.0.0.1:8088";
        if (s_clientCertPath is not null)
        {
            psi.EnvironmentVariables["AURAGRID_CLIENT_CERT_PATH"] = s_clientCertPath;
            psi.EnvironmentVariables["AURAGRID_CLIENT_CERT_PASSWORD"] = s_clientCertPassword;
        }
        if (s_ipcToken is not null)
        {
            psi.EnvironmentVariables["AURAGRID_IPC_TOKEN"] = s_ipcToken;
        }
        var process = System.Diagnostics.Process.Start(psi);
        if (process is null) { Console.WriteLine("    Could not start process."); return; }

        using var cts = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(timeoutSeconds));
        var outTask = process.StandardOutput.ReadToEndAsync();
        var errTask = process.StandardError.ReadToEndAsync();
        try { await process.WaitForExitAsync(cts.Token); }
        catch (OperationCanceledException)
        {
            Console.WriteLine($"    [{label}] Timed out after {timeoutSeconds}s — killing.");
            try { process.Kill(entireProcessTree: true); } catch { }
        }
        var stdout = await outTask;
        var stderr = await errTask;

        if (!string.IsNullOrWhiteSpace(stdout))
            Console.WriteLine("    STDOUT: " + stdout.Trim().Replace("\n", "\n    "));
        if (!string.IsNullOrWhiteSpace(stderr))
            Console.WriteLine("    STDERR: " + stderr.Trim().Replace("\n", "\n    "));
        Console.WriteLine($"    Exit code: {process.ExitCode}");
    }

    enum AppKind { Python, DotNet }

    record AppEntry(string Id, AppKind Kind, string? SmokeExe = null);
}
